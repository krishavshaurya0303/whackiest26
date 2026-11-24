"""
llm.py - MendMap's "brain".

ask_llm(prompt) sends a prompt to an AI model and returns its text reply.

Pick the provider with LLM_PROVIDER in your .env file:
  bedrock -> AWS Bedrock (e.g. a Claude model)   [counts for the AWS sponsor prize]
  gemini  -> Google Gemini (free API key)
  mock    -> no AI at all; agent.py uses simple rules instead (demo never breaks)
"""
import os

PROVIDER = os.getenv("LLM_PROVIDER", "mock").strip().lower()


def ask_llm(prompt: str) -> str:
    """Send one prompt, get one text answer. Raises an error if anything fails."""
    if PROVIDER == "bedrock":
        import boto3  # AWS SDK for Python

        client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))
        # "converse" is Bedrock's standard chat API; the model ID comes from your Bedrock console
        resp = client.converse(
            modelId=os.environ["BEDROCK_MODEL_ID"],
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 1500, "temperature": 0},
        )
        return resp["output"]["message"]["content"][0]["text"]

    if PROVIDER == "gemini":
        from google import genai  # Google's Gemini SDK

        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        resp = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),  # check the current model name in Google AI Studio
            contents=prompt,
        )
        return resp.text

    # "mock" (or anything unknown): tell the agent to use its rule-based fallback
    raise RuntimeError("LLM_PROVIDER is mock - using rule-based fallback")
