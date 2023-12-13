from langchain.prompts import ChatPromptTemplate

from ragas.llms import RagasLLM
from ragas.testset.prompts import FILTER_QUESTION, SCORE_CONTEXT, SEED_QUESTION
from ragas.testset.testset_generator import load_as_score
from ragas.utils import load_as_json


def filter_context(llm: RagasLLM, context: str, threshold: float = 7.5) -> bool:
    """
    context: str
        The input context

    Checks if the context is has information worthy of framing a question
    """
    human_prompt = SCORE_CONTEXT.format(context=context)
    prompt = ChatPromptTemplate.from_messages([human_prompt])
    results = llm.generate(prompts=[prompt])
    output = results.generations[0][0].text.strip()
    score = load_as_score(output)
    return score >= threshold


def filter_question(llm: RagasLLM, question: str) -> bool:
    human_prompt = FILTER_QUESTION.format(question=question)
    prompt = ChatPromptTemplate.from_messages([human_prompt])

    results = llm.generate(prompts=[prompt])
    results = results.generations[0][0].text.strip()
    json_results = load_as_json(results)
    return json_results.get("verdict") != "No"


def simple_evolution(llm: RagasLLM, context: str):
    human_prompt = SEED_QUESTION.format(context=context)
    prompt = ChatPromptTemplate.from_messages([human_prompt])
    results = llm.generate(prompts=[prompt])
    question = results.generations[0][0].text.strip()
    return question
