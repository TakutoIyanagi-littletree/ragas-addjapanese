# ✨ Introduction

Ragas is a library that provides tools to supercharge the evaluation of Large Language Model (LLM) applications. It is designed to help you evaluate your LLM applications with ease and confidence. 



<div class="grid cards" markdown>
- 🚀 **Get Started**

    Install with `pip` and get started with Ragas with these tutorials.

    [:octicons-arrow-right-24: Get Started](getstarted/index.md)

- 📚 **Core Concepts**

    In depth explanation and discussion of the concepts and working of different features available in Ragas.

    [:octicons-arrow-right-24: Core Concepts](concepts/index.md)

- 🛠️ **How-to Guides**

    Practical guides to help you achieve a specific goals. Take a look at these
    guides to learn how to use Ragas to solve real-world problems.

    [:octicons-arrow-right-24: How-to Guides](howtos/index.md)

- 📖 **References**

    Technical descriptions of how Ragas classes and methods work.

    [:octicons-arrow-right-24: References](references/index.md)

</div>


## Frequently Asked Questions

<details>
<summary>What is the best open-source model to use?</summary>

There isn't a single correct answer to this question. With the rapid pace of AI model development, new open-source models are released every week, often claiming to outperform previous versions. The best model for your needs depends largely on your GPU capacity and the type of data you're working with. 

It's a good idea to explore newer, widely accepted models with strong general capabilities. You can refer to [this list](https://github.com/eugeneyan/open-llms?tab=readme-ov-file#open-llms) for available open-source models, their release dates, and fine-tuned variants.
</details>

<details>
<summary>Why do NaN values appear in evaluation results?</summary>

NaN stands for "Not a Number." In ragas evaluation results, NaN can appear for two main reasons:
- The model's output is not JSON-parsable. ragas requires models to output JSON-compatible responses because all prompts are structured using Pydantic. This ensures efficient parsing of LLM outputs.
- Certain cases in the sample may not be ideal for scoring. For example, scoring the faithfulness of a response like "I don’t know" might not be appropriate.

</details>

<details>
<summary>How can I make evaluation results more explainable?</summary>

The best way is to trace and log your evaluation, then inspect the results using LLM traces. You can follow a detailed example of this process [here](https://docs.ragas.io/en/stable/howtos/customizations/metrics/tracing/).

</details>