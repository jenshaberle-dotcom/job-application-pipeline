# Origin LLM smoke contract v1

The first live model-campaign run is a transport and boundary smoke test, not a quality benchmark.

- campaign mode: `benchmark`
- benchmark cases: `1`
- models: `gpt-5.4-mini,gpt-5.6-terra,gpt-5.5`
- exact maximum provider requests: `3`
- retry policy: no application-level retry
- cost handling: measured and reported, never used as a stop gate
- output boundary: `review_output_only_not_pipeline_input`
- mutation authority: none

The request envelope is the safety control. Benchmark request capacity must equal case count multiplied by model count. Provider failures stop closed and are not retried by the application.
