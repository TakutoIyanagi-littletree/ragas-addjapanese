from __future__ import annotations

import typing as t

from llms import llm, llm_async
from metrics import GenerationMetric

SHORT_FORM_ANSWER = """Given a question and answer, create a statement.
question: Who is the president of India?
answer: Narendra Modi
statement: Narendara Modi is the president of India.
question: Which magazine was started first Arthur's Magazine or Women's Magazine?
answer: Arthur's Magazine
statement: Arthur's Magazine started before Women's magazine. 
question: Cadmium Chloride is slightly soluble in this chemical, it is also called what?
answer: alochol
statement: Cadmium Chloride is slightly soluble in alcohol.
question: Were Shahul and Jithin of the same nationality?
answer: They were from different countries.
statement: Shahul and Jithin were from different countries.
question: {}
answer: {}
statemtent:"""

LONG_FORM_ANSWER = """
Given a question and answer, create one or more statements from answer.
question: Who was  Albert Einstein and what is he best known for?
answer: He was a German-born theoretical physicist, widely acknowledged to be one of the greatest and most influential physicists of all time. He was best known for developing the theory of relativity, he also made important contributions to the development of the theory of quantum mechanics.
statements:\nAlbert Einstein was born in Germany.\nAlbert Einstein was best known for his theory of relativity.
question:{}
answer: {}
statements:\n"""

NLI_STATEMENTS = """
Prompt: Natural language inference
Consider the following context:
Context:
John is a student at XYZ University. He is pursuing a degree in Computer Science. He is enrolled in several courses this semester, including Data Structures, Algorithms, and Database Management. John is a diligent student and spends a significant amount of time studying and completing assignments. He often stays late in the library to work on his projects.
Now, read the following statements and determine whether they are supported by the information present in the context. Provide a brief explanation for each statement. Also provide a Final Answer (Yes/No) at the end. 
statements:\n1. John is majoring in Biology.\n2. John is taking a course on Artificial Intelligence.\n3. John is a dedicated student.\n4. John has a part-time job.\n5. John is interested in computer programming.\n
Answer:
1. John is majoring in Biology.
Explanation: John's major is explicitly mentioned as Computer Science. There is no information suggesting he is majoring in Biology. So answer is No.
2. John is taking a course on Artificial Intelligence.
Explanation: The context mentions the courses John is currently enrolled in, and Artificial Intelligence is not mentioned. Therefore, it cannot be deduced that John is taking a course on AI.So answer is No.
3. John is a dedicated student.
Explanation: The prompt states that he spends a significant amount of time studying and completing assignments. Additionally, it mentions that he often stays late in the library to work on his projects, which implies dedication.So answer is Yes.
4. John has a part-time job.
Explanation: There is no information given in the context about John having a part-time job. Therefore, it cannot be deduced that John has a part-time job. So answer is No.
5. John is interested in computer programming.
Explanation: The context states that John is pursuing a degree in Computer Science, which implies an interest in computer programming.So answer is Yes.
Final answer: No. No. Yes. No. Yes.
context:\n{}
statements:\n{}
Now, read the following statements and determine whether they are supported by the information present in the context. Provide a brief explanation for each statement. Also provide a Final Answer (Yes/No) at the end. 
Answer:
"""


class NLIScore(GenerationMetric):
    @property
    def name(self):
        return "NLI_score"

    @property
    def is_batchable(self: t.Self):
        return True

    def init_model(self: t.Self):
        pass

    def score(
        self: t.Self,
        questions: list[str],
        contexts: list[list[str]],
        answers: list[str],
    ):
        """
        returns the NLI score for each (q, c, a) pair
        """

        prompts = []
        for question, answer in zip(questions, answers):
            if (len(answer.split()) < 4) or (len(answer.split(".")) == 1):
                prompt = SHORT_FORM_ANSWER.format(question, answer)
                prompts.append(prompt)
            else:
                prompt = LONG_FORM_ANSWER.format(question, answer)
                prompts.append(prompt)

        response = llm(prompts)
        usage = response["usage"]
        print(usage)
        list_statements = []
        for output in response["choices"]:
            statements = output["text"].split("\n")
            list_statements.append(statements)


        prompts = []
        for context, statements in zip(contexts, list_statements):
            statements = "\n".join([f'{i+1}.{st}' for i, st in enumerate(statements)])
            prompt = NLI_STATEMENTS.format(context, statements)
            prompts.append(prompt)

        response = llm(prompts)
        outputs = response["choices"]
        usage = response["usage"]
        print(usage)

        scores = []
        for i, output in enumerate(outputs):
            output = output['text'].lower().strip()
            if output.find("final answer:") != -1:
                output = output[output.find("final answer:") + len("final answer:"):]
                score = sum(0 if "yes" in answer else 1 for answer in output.strip().split(".") if answer != '')
                score = score / len(list_statements[i])
            else:
                score = max(0, output.count("so answer is no")) / len(list_statements[i])
            
            scores.append(1 - score)

        return scores


NLI = NLIScore()
