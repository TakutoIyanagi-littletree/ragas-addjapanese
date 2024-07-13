from __future__ import annotations

import logging
import typing as t
from dataclasses import dataclass, field

import numpy as np
from langchain.pydantic_v1 import BaseModel, Field

from ragas.llms.output_parser import RagasoutputParser, get_json_format_instructions
from ragas.llms.prompt import Prompt, PromptValue
from ragas.metrics.base import EvaluationMode, MetricWithLLM, ensembler

if t.TYPE_CHECKING:
    from langchain_core.callbacks import Callbacks

logger = logging.getLogger(__name__)


class ContextUtilizationVerification(BaseModel):
    """Answer for the verification task wether the context was useful."""

    reason: str = Field(..., description="Reason for verification")
    verdict: int = Field(..., description="Binary (0/1) verdict of verification")


class ContextPrecisionVerifications(BaseModel):
    __root__: t.List[ContextUtilizationVerification]


_verification_output_instructions = get_json_format_instructions(
    ContextUtilizationVerification
)
_output_parser = RagasoutputParser(pydantic_object=ContextUtilizationVerification)

CONTEXT_UTILIZATION = Prompt(
    name="context_utilization",
    instruction="""Given question, answer and context verify if the context was useful in arriving at the given answer. Give verdict as "1" if useful and "0" if not with json output.""",
    output_format_instruction=_verification_output_instructions,
    examples=[
        {
            "question": """What can you tell me about albert Albert Einstein?""",
            "context": """Albert Einstein (14 March 1879 – 18 April 1955) was a German-born theoretical physicist, widely held to be one of the greatest and most influential scientists of all time. Best known for developing the theory of relativity, he also made important contributions to quantum mechanics, and was thus a central figure in the revolutionary reshaping of the scientific understanding of nature that modern physics accomplished in the first decades of the twentieth century. His mass–energy equivalence formula E = mc2, which arises from relativity theory, has been called "the world's most famous equation". He received the 1921 Nobel Prize in Physics "for his services to theoretical physics, and especially for his discovery of the law of the photoelectric effect", a pivotal step in the development of quantum theory. His work is also known for its influence on the philosophy of science. In a 1999 poll of 130 leading physicists worldwide by the British journal Physics World, Einstein was ranked the greatest physicist of all time. His intellectual achievements and originality have made Einstein synonymous with genius.""",
            "answer": """Albert Einstein born in 14 March 1879 was German-born theoretical physicist, widely held to be one of the greatest and most influential scientists of all time. He received the 1921 Nobel Prize in Physics for his services to theoretical physics. He published 4 papers in 1905. Einstein moved to Switzerland in 1895""",
            "verification": ContextUtilizationVerification(
                reason="The provided context was indeed useful in arriving at the given answer. The context includes key information about Albert Einstein's life and contributions, which are reflected in the answer.",
                verdict=1,
            ).dict(),
        },
        {
            "question": """who won 2020 icc world cup?""",
            "context": """The 2022 ICC Men's T20 World Cup, held from October 16 to November 13, 2022, in Australia, was the eighth edition of the tournament. Originally scheduled for 2020, it was postponed due to the COVID-19 pandemic. England emerged victorious, defeating Pakistan by five wickets in the final to clinch their second ICC Men's T20 World Cup title.""",
            "answer": """England""",
            "verification": ContextUtilizationVerification(
                reason="the context was useful in clarifying the situation regarding the 2020 ICC World Cup and indicating that England was the winner of the tournament that was intended to be held in 2020 but actually took place in 2022.",
                verdict=1,
            ).dict(),
        },
        {
            "question": """What is the tallest mountain in the world?""",
            "context": """The Andes is the longest continental mountain range in the world, located in South America. It stretches across seven countries and features many of the highest peaks in the Western Hemisphere. The range is known for its diverse ecosystems, including the high-altitude Andean Plateau and the Amazon rainforest.""",
            "answer": """Mount Everest.""",
            "verification": ContextUtilizationVerification(
                reason="the provided context discusses the Andes mountain range, which, while impressive, does not include Mount Everest or directly relate to the question about the world's tallest mountain.",
                verdict=0,
            ).dict(),
        },
    ],
    input_keys=["question", "context", "answer"],
    output_key="verification",
    output_type="json",
)


@dataclass
class ContextUtilization(MetricWithLLM):
    """
    Average Precision is a metric that evaluates whether all of the
    relevant items selected by the model are ranked higher or not.

    Attributes
    ----------
    name : str
    evaluation_mode: EvaluationMode
    context_precision_prompt: Prompt
    """

    name: str = "context_utilization"  # type: ignore
    evaluation_mode: EvaluationMode = EvaluationMode.qac  # type: ignore
    context_utilization_prompt: Prompt = field(
        default_factory=lambda: CONTEXT_UTILIZATION
    )
    max_retries: int = 1
    _reproducibility: int = 1

    @property
    def reproducibility(self):
        return self._reproducibility

    @reproducibility.setter
    def reproducibility(self, value):
        if value < 1:
            logger.warning("reproducibility cannot be less than 1, setting to 1")
            value = 1
        elif value % 2 == 0:
            logger.warning(
                "reproducibility level cannot be set to even number, setting to odd"
            )
            value += 1
        self._reproducibility = value

    def _context_utilization_prompt(self, row: t.Dict) -> t.List[PromptValue]:
        question, contexts, ground_truth = (
            row["question"],
            row["contexts"],
            row["ground_truth"],
        )
        return [
            self.context_utilization_prompt.format(
                question=question, context=c, answer=ground_truth
            )
            for c in contexts
        ]

    def _calculate_average_precision(
        self, verifications: t.List[ContextUtilizationVerification]
    ) -> float:
        score = np.nan

        verdict_list = [1 if ver.verdict else 0 for ver in verifications]
        denominator = sum(verdict_list) + 1e-10
        numerator = sum(
            [
                (sum(verdict_list[: i + 1]) / (i + 1)) * verdict_list[i]
                for i in range(len(verdict_list))
            ]
        )
        score = numerator / denominator
        if np.isnan(score):
            logger.warning(
                "Invalid response format. Expected a list of dictionaries with keys 'verdict'"
            )
        return score

    async def _ascore(
        self: t.Self,
        row: t.Dict,
        callbacks: Callbacks,
        is_async: bool,
    ) -> float:
        assert self.llm is not None, "LLM is not set"

        human_prompts = self._context_utilization_prompt(row)
        responses = []
        for hp in human_prompts:
            results = await self.llm.generate(
                hp,
                callbacks=callbacks,
                is_async=is_async,
                n=self.reproducibility,
            )
            results = [
                await _output_parser.aparse(item.text, hp, self.llm, self.max_retries)
                for item in results.generations[0]
            ]

            responses.append(
                [result.dict() for result in results if result is not None]
            )

        answers = []
        for response in responses:
            agg_answer = ensembler.from_discrete([response], "verdict")
            if agg_answer:
                agg_answer = ContextUtilizationVerification.parse_obj(agg_answer[0])
            answers.append(agg_answer)

        answers = ContextPrecisionVerifications(__root__=answers)
        score = self._calculate_average_precision(answers.__root__)
        return score

    def adapt(self, language: str, cache_dir: str | None = None) -> None:
        assert self.llm is not None, "LLM is not set"

        logging.info(f"Adapting Context Utilization to {language}")
        self.context_utilization_prompt = self.context_utilization_prompt.adapt(
            language, self.llm, cache_dir
        )

    def save(self, cache_dir: str | None = None) -> None:
        self.context_utilization_prompt.save(cache_dir)


context_utilization = ContextUtilization()
