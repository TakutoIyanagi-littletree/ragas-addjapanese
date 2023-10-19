"""
Q - question
A - answer: generated_text from RAG pipeline
C - contexts: context used for generation
G - ground_truths: ground truth answer
"""
from __future__ import annotations

import logging
import os
import typing as t
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from math import floor

from datasets import Dataset
from langchain.callbacks.manager import CallbackManager, trace_as_chain_group
from langchain.chat_models import ChatOpenAI
from tqdm import tqdm

from ragas.metrics.llms import LangchainLLM

if t.TYPE_CHECKING:
    from langchain.callbacks.base import Callbacks


def make_batches(total_size: int, batch_size: int) -> list[range]:
    """
    Take a total size and batch size and return a list of ranges for the batches
    """
    tail = total_size % batch_size
    num_batches = floor(total_size / batch_size)
    batches = [
        range(i, i + batch_size) for i in range(0, batch_size * num_batches, batch_size)
    ]
    if tail != 0:
        batches.append(range(batch_size * num_batches, batch_size * num_batches + tail))

    return batches


EvaluationMode = Enum("EvaluationMode", "qac qa qc gc ga qga")


@dataclass
class Metric(ABC):
    batch_size: int

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def evaluation_mode(self) -> EvaluationMode:
        ...

    @abstractmethod
    def init_model():
        """
        This method will lazy initialize the model.
        """
        ...

    def score(
        self: t.Self,
        dataset: Dataset,
        callbacks: t.Optional[Callbacks] = None,
    ) -> Dataset:
        scores = []
        cm = CallbackManager.configure(inheritable_callbacks=callbacks)
        with trace_as_chain_group(f"ragas_{self.name}", callback_manager=cm) as group:
            for batch in tqdm(self.get_batches(len(dataset))):
                score = self._score_batch(dataset.select(batch), callbacks=group)
                scores.extend(score)

        return dataset.add_column(f"{self.name}", scores)  # type: ignore

    @abstractmethod
    def _score_batch(
        selfself: t.Self,
        dataset: Dataset,
        callbacks: t.Optional[Callbacks] = None,
        callback_group_name: str = "batch",
    ) -> list:
        ...

    def score_single(
        self: t.Self,
        ds_row: dict,
        callbacks: t.Optional[Callbacks] = None,
    ) -> float:
        """
        Score for a single row of dataset
        """
        # TODO: validation check if they are string

        ds = Dataset.from_dict({k: [v] for k, v in ds_row.items()})
        score = self._score_batch(
            ds, callback_group_name=self.name, callbacks=callbacks
        )

        return score[0]

    def get_batches(self, dataset_size: int) -> list[range]:
        return make_batches(dataset_size, self.batch_size)


def _llm_factory() -> LangchainLLM:
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if openai_api_key is None:
        logging.warning(
            "OPENAI_API_KEY is not set! Make sure your passing 'OPENAI_API_KEY' env variable."  # noqa
        )
    openai_llm = ChatOpenAI(
        model_name="gpt-3.5-turbo-16k", openai_api_key=openai_api_key  # type: ignore
    )
    return LangchainLLM(openai_llm)


@dataclass
class MetricWithLLM(Metric):
    llm: LangchainLLM = field(default_factory=_llm_factory)
