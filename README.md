# gemini-code-review-action-full-context

A container GitHub Action to review a pull request by Gemini AI, considering the full context of the project.

This action analyzes the entire project structure and content, followed by the pull request diff. It provides a comprehensive review that takes into account the broader context of the changes.

If the size of a pull request is over the maximum chunk size of the Gemini API, the Action will split the pull request into multiple chunks and generate review comments for each chunk.
The Action then summarizes the review comments and posts a review comment to the pull request.

## Pre-requisites

Set a GitHub Actions secret `GEMINI_API_KEY` to use the Gemini API securely.

## Inputs

- `gemini_api_key`: The Gemini API key to access the Gemini API [(GET MY API KEY)](https://makersuite.google.com/app/apikey).
- `github_token`: The GitHub token to access the GitHub API (You do not need to generate this Token!).
- `github_repository`: The GitHub repository to post a review comment.
- `github_pull_request_number`: The GitHub pull request number to post a review comment.
- `git_commit_hash`: The git commit hash to post a review comment.
- `pull_request_diff`: The diff of the pull request to generate a review comment.
- `pull_request_diff_chunk_size`: The chunk size of the diff of the pull request to generate a review comment.
- `extra_prompt`: The extra prompt to generate a review comment.
- `model`: The model to generate a review comment. We can use any available model.
- `log_level`: The log level to print logs.

Note: The Gemini model has a limitation on the maximum number of input tokens. If the size of the diff exceeds this limit, it will be split into multiple chunks. You can adjust the chunk size based on the model you use.

## Example usage

Here's an example of how to use the Action to review a pull request in your repository:

```yaml
name: "Code Review by Gemini AI"

on:
  pull_request:

jobs:
  review:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@v3
      - name: "Get diff of the pull request"
        id: get_diff
        shell: bash
        env:
          PULL_REQUEST_HEAD_REF: "${{ github.event.pull_request.head.ref }}"
          PULL_REQUEST_BASE_REF: "${{ github.event.pull_request.base.ref }}"
        run: |-
          git fetch origin "${{ env.PULL_REQUEST_HEAD_REF }}"
          git fetch origin "${{ env.PULL_REQUEST_BASE_REF }}"
          git checkout "${{ env.PULL_REQUEST_HEAD_REF }}"
          git diff "origin/${{ env.PULL_REQUEST_BASE_REF }}" > "diff.txt"
          {
            echo "pull_request_diff<<EOF";
            cat "diff.txt";
            echo 'EOF';
          } >> $GITHUB_OUTPUT
      - uses: M0ch0/gemini-code-review-action-full-context@0.1.1
        name: "Code Review by Gemini AI"
        id: review
        with:
          gemini_api_key: ${{ secrets.GEMINI_API_KEY }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
          github_repository: ${{ github.repository }}
          github_pull_request_number: ${{ github.event.pull_request.number }}
          git_commit_hash: ${{ github.event.pull_request.head.sha }}
          model: "gemini-1.5-pro-exp-0827"
          pull_request_diff: |-
            ${{ steps.get_diff.outputs.pull_request_diff }}
          pull_request_chunk_size: "1500000"
          extra_prompt: |-
            Code reviews need to be multifaceted, critical, thoughtful and excellent.
          log_level: "DEBUG"
```


## Output

The Action posts a review comment to the pull request, which includes (if gemini works well):

1. A summary of the pull request structure and any notable patterns or issues
2. Comments on specific files or sections of the pull request that require attention, if any
3. Detailed analysis of the changes in the pull request, if any
4. Suggestions for improvements or alternative implementations, if any
5. Conclusion and Approval/Rejection of the pull request