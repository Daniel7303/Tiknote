from openai import OpenAI

client = OpenAI(api_key="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")


response = client.responses.create(
    model = "gpt-5",
    input = "write me a short bedtime story"
)


print(response.output_text)