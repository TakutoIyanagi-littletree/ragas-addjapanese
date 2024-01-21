from __future__ import annotations

import logging
import typing as t
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from fsspec.exceptions import asyncio
from numpy.random import default_rng

from ragas.llms import BaseRagasLLM
from ragas.llms.json_load import load_as_json
from ragas.testset.docstore import Direction, Document, DocumentStore, Node
from ragas.testset.prompts import (
    context_scoring_prompt,
    filter_question_prompt,
    multi_context_question_prompt,
    seed_question_prompt,
    compress_question_prompt,
)

rng = default_rng()
logger = logging.getLogger(__name__)

if t.TYPE_CHECKING:
    from ragas.llms.prompt import Prompt


@dataclass
class Filter(ABC):
    ...


@dataclass
class NodeFilter(Filter):
    llm: BaseRagasLLM
    threshold: float = 7.5

    def filter(self, node: Node) -> t.Dict:
        return asyncio.get_event_loop().run_until_complete(self.afilter(node))

    async def afilter(self, node: Node) -> t.Dict:
        prompt = context_scoring_prompt.format(context=node.page_content)
        results = await self.llm.agenerate_text(prompt=prompt)
        output = results.generations[0][0].text.strip()
        score = load_as_json(output)
        score.update({"score": score.get("score", 0) >= self.threshold})
        return score


@dataclass
class QuestionFilter(Filter):
    llm: BaseRagasLLM

    def filter(self, question: str) -> bool:
        return asyncio.get_event_loop().run_until_complete(self.afilter(question))

    async def afilter(self, question: str) -> bool:
        prompt = filter_question_prompt.format(question=question)
        results = await self.llm.agenerate_text(prompt=prompt)
        results = results.generations[0][0].text.strip()
        json_results = load_as_json(results)
        logger.debug("filtered question: %s", json_results)
        return json_results.get("verdict") != "No"


@dataclass
class Evolution:
    node_filter: NodeFilter
    question_filter: QuestionFilter
    nodes: t.List[Node] = field(default_factory=list)
    max_tries: int = 5
    _root_node: t.Optional[Node] = field(default=None, init=False, repr=False)
    _tries: int = field(default=0, init=False, repr=False)

    def merged_nodes(self) -> Node:
        return Node(
            doc_id="merged", page_content=" ".join(n.page_content for n in self.nodes)
        )

    async def aretry_evolve(
        self, llm: BaseRagasLLM, docstore: DocumentStore, update_count: bool = True
    ):
        if update_count:
            self._tries += 1
        logger.info("retrying evolution: %s times", self._tries)
        if self._tries > self.max_tries:
            # TODO: make this into a custom exception
            raise ValueError("Max tries reached")
        return await self.aevolve(llm, docstore)

    @abstractmethod
    def evolve(self, llm: BaseRagasLLM, docstore: DocumentStore) -> str:
        ...

    @abstractmethod
    async def aevolve(self, llm: BaseRagasLLM, docstore: DocumentStore) -> str:
        ...


@dataclass
class SimpleEvolution(Evolution):
    def evolve(self, llm: BaseRagasLLM, docstore: DocumentStore):
        logger.info("evolving question")
        return asyncio.get_event_loop().run_until_complete(self.aevolve(llm, docstore))

    def _get_more_adjacent_nodes(self, docstore: DocumentStore):
        """
        if the evolutions doesn't have enough nodes to frame a question, get more nodes
        """
        assert self._root_node is not None, "root node cannot be None"
        # get more nodes from above the context window
        prev_adjacent_node = docstore.get_adjacent(self._root_node, Direction.PREV)
        if prev_adjacent_node is None:
            # get more nodes from below the context window
            next_adjacent_node = docstore.get_adjacent(self._root_node, Direction.NEXT)
            if next_adjacent_node is not None:
                # add next nodes towards the end
                self.nodes.append(next_adjacent_node)
            else:
                # retry with new base node
                self.nodes = docstore.get_random_nodes(k=1)
                self._root_node = self.nodes[0]
        else:
            # add prev nodes in index 0
            self.nodes.insert(0, prev_adjacent_node)

    async def aevolve(self, llm: BaseRagasLLM, docstore: DocumentStore):
        # can the node be used to frame a question?
        if self._tries == 0:
            self.nodes = docstore.get_random_nodes(k=1)
            self._root_node = self.nodes[0]
        merged_node = self.merged_nodes()
        passed = await self.node_filter.afilter(self.nodes[0])
        if not passed["score"]:
            self.nodes = docstore.get_random_nodes(k=1)
            return await self.aretry_evolve(llm, docstore, update_count=False)

        results = llm.generate_text(
            prompt=seed_question_prompt.format(context=merged_node.page_content)
        )
        seed_question = results.generations[0][0].text
        # NOTE: might need improvement
        # select only one seed question here
        is_valid_question = await self.question_filter.afilter(seed_question)
        if not is_valid_question:
            # get more context to rewrite question
            self._get_more_adjacent_nodes(docstore)
            # retry with new nodes added
            return await self.aretry_evolve(llm, docstore)
        else:
            # if valid question
            return seed_question


@dataclass
class MultiContextEvolution(Evolution):
    se: SimpleEvolution = field(init=False, repr=False)

    def __post_init__(self):
        # init simple evolution to get seed question
        self.se = SimpleEvolution(self.node_filter, self.question_filter)

    def _transform_question(
        self, llm: BaseRagasLLM, prompt: Prompt, question: str
    ) -> str:
        results = llm.generate_text(prompt=prompt.format(question=question))
        return results.generations[0][0].text.strip()

    def evolve(self, llm: BaseRagasLLM, docstore: DocumentStore):
        logger.info("evolving question")
        return asyncio.get_event_loop().run_until_complete(self.aevolve(llm, docstore))

    async def aevolve(self, llm: BaseRagasLLM, docstore: DocumentStore) -> str:
        # gerenate seed question
        self._root_node = docstore.get_random_nodes(k=1)[0]
        question = await self.se.aevolve(llm, docstore)
        logger.debug("[MultiContextEvolution] simple question generated: %s", question)

        # find a similar node and generate a question based on both
        similar_context = docstore.get_similar(self._root_node)[0]
        prompt = multi_context_question_prompt.format(
            question=question,
            context1=self._root_node.page_content,
            context2=similar_context,
        )
        results = await llm.agenerate_text(prompt=prompt)
        question = results.generations[0][0].text.strip()
        logger.debug(
            "[MultiContextEvolution] multicontext question generated: %s", question
        )

        # compress the question
        compressed_question = self._transform_question(
            llm=llm, prompt=compress_question_prompt, question=question
        )
        logger.debug(
            "[MultiContextEvolution] multicontext question compressed: %s", question
        )

        return compressed_question
