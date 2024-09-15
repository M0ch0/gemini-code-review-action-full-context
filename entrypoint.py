#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#          http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
import json
import os
from typing import List

import click
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import requests
from loguru import logger


def check_required_env_vars():
    """Check required environment variables"""
    required_env_vars = [
        "GEMINI_API_KEY",
        "GITHUB_TOKEN",
        "GITHUB_REPOSITORY",
        "GITHUB_PULL_REQUEST_NUMBER",
        "GIT_COMMIT_HASH",
    ]
    for required_env_var in required_env_vars:
        if os.getenv(required_env_var) is None:
            raise ValueError(f"{required_env_var} is not set")


def get_review_prompt(extra_prompt: str = "") -> str:
    """Get a prompt template"""
    template = f"""
    You are reviewing pull request. The context provided includes the entire project structure and content, followed by the pull request diff.

    As an excellent software engineer and security expert, please analyze the pull request (just the pull request. The whole project is just a reference, so you don't need to review the whole thing, just the pull request) Consider the following:

    1. Overall pull request structure and code quality
    2. Potential security vulnerabilities in the changed code, if any
    3. Changes introduced in the pull request
    4. Improvements or issues in the pull request, if any
    5. Suggestions for better code organization, performance, or security, if any

    Provide a comprehensive review that includes:
    - A summary of the pull request structure and any notable patterns or issues
    - Comments on specific files or sections of pull request that require attention
    - Detailed analysis of the changes in the pull request
    - Suggestions for improvements or alternative implementations, if any
    - Conclusion and Approval/Rejection of the pull request

    {extra_prompt}

    Please begin your review now.
    """
    return template

def get_summarize_prompt() -> str:
    """Get a prompt template"""
    template = """
    Please provide a concise summary of your review, highlighting the most important findings and recommendations. Focus on:

    1. Key strengths and weaknesses of the pull request, if any
    2. Critical issues or improvements needed in the pull request, if any
    3. High-priority security concerns, if any

    Your summary should give a clear overview of the impact of the pull request.
    """
    return template


def create_a_comment_to_pull_request(
        github_token: str,
        github_repository: str,
        pull_request_number: int,
        git_commit_hash: str,
        body: str):
    """Create a comment to a pull request"""
    headers = {
        "Accept": "application/vnd.github.v3.patch",
        "authorization": f"Bearer {github_token}"
    }
    data = {
        "body": body,
        "commit_id": git_commit_hash,
        "event": "COMMENT"
    }
    url = f"https://api.github.com/repos/{github_repository}/pulls/{pull_request_number}/reviews"
    response = requests.post(url, headers=headers, data=json.dumps(data))
    return response


def chunk_string(input_string: str, chunk_size) -> List[str]:
    """Chunk a string"""
    chunked_inputs = []
    for i in range(0, len(input_string), chunk_size):
        chunked_inputs.append(input_string[i:i + chunk_size])
    return chunked_inputs


def get_review(
        context: str,
        diff: str,
        extra_prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        top_p: float,
        frequency_penalty: float,
        presence_penalty: float
):
    """Get a review focusing on the PR changes"""
    review_prompt = get_review_prompt(extra_prompt=extra_prompt)
    generation_config = {
        "temperature": temperature,
        "top_p": top_p,
        "top_k": 40,
        "max_output_tokens": max_tokens,
    }
    
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }
    
    genai_model = genai.GenerativeModel(model_name=model, generation_config=generation_config, safety_settings=safety_settings)
    
    # Combine context, review prompt, and diff
    full_input = f"{review_prompt}\n\nProject Context:\n{context}\n\nPull Request Changes:\n{diff}"
    
    review_result = genai_model.generate_content(full_input, generation_config=generation_config, safety_settings=safety_settings)
    logger.debug(f"Response AI: {review_result}")

    return review_result

def read_project_files(exclude_dirs=['.github', '.idea']):
    project_content = []
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            if file.endswith(('.py', '.yml', '.yaml', '.md', '.txt', '.json', '.kt', '.html', '.js',
                              '.ts', '.css', '.java', '.c', '.cpp', '.h', '.hpp', '.go', '.rs', '.swift',
                              '.sh', '.rb', '.php', '.mdx', '.rs', '.sql', '.ini', '.cfg', '.conf', '.toml',
                              '.env', '.cfg', '.conf', '.toml', '.ini', '.txt', '.xml')):
                file_path = os.path.join(root, file)
                with open(file_path, 'r') as f:
                    content = f.read()
                project_content.append(f"File: {file_path}\n\n ```{content}```\n\n")
    return '\n'.join(project_content)


@click.command()
@click.option("--diff", type=click.STRING, required=True, help="Pull request diff")
@click.option("--diff-chunk-size", type=click.INT, required=False, default=3500, help="Pull request diff")
@click.option("--model", type=click.STRING, required=False, default="gemini-1.5-flash", help="Model")
@click.option("--extra-prompt", type=click.STRING, required=False, default="", help="Extra prompt")
@click.option("--temperature", type=click.FLOAT, required=False, default=0.1, help="Temperature")
@click.option("--max-tokens", type=click.INT, required=False, default=8192, help="Max tokens")
@click.option("--top-p", type=click.FLOAT, required=False, default=1.0, help="Top N")
@click.option("--frequency-penalty", type=click.FLOAT, required=False, default=0.0, help="Frequency penalty")
@click.option("--presence-penalty", type=click.FLOAT, required=False, default=0.0, help="Presence penalty")
@click.option("--log-level", type=click.STRING, required=False, default="INFO", help="Presence penalty")
def main(
        diff: str,
        diff_chunk_size: int,
        model: str,
        extra_prompt: str,
        temperature: float,
        max_tokens: int,
        top_p: float,
        frequency_penalty: float,
        presence_penalty: float,
        log_level: str
):
    # Set log level
    logger.level(log_level)
    # Check if necessary environment variables are set or not
    check_required_env_vars()

    # Set the Gemini API key
    api_key = os.getenv("GEMINI_API_KEY")
    genai.configure(api_key=api_key)

    # Read the entire project content
    project_content = read_project_files()

    logger.debug(f"Project content: {project_content}")
    
    # Request a code review
    review = get_review(
        context=project_content,
        diff=diff,
        extra_prompt=extra_prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        frequency_penalty=frequency_penalty,
        presence_penalty=presence_penalty
    )
    
    logger.debug(f"Review: {review}")

    # Format reviews

    # Create a comment to a pull request
    create_a_comment_to_pull_request(
        github_token=os.getenv("GITHUB_TOKEN"),
        github_repository=os.getenv("GITHUB_REPOSITORY"),
        pull_request_number=int(os.getenv("GITHUB_PULL_REQUEST_NUMBER")),
        git_commit_hash=os.getenv("GIT_COMMIT_HASH"),
        body=review
    )


if __name__ == "__main__":
    # pylint: disable=no-value-for-parameter
    main()
