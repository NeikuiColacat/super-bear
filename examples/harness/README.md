# Harness smoke examples

These files show the smallest plug-and-play contract for Pi, Codex, or another
external harness.

## Validate the sample result

```bash
uv run python -m packages.harness.cli < examples/harness/validation_payload.sample.json
```

Expected output:

```json
{"errors": [], "ok": true}
```

Pi may wrap JSON in Markdown fences. This is also accepted at the harness
boundary:

```bash
uv run python -m packages.harness.cli < examples/harness/validation_payload_from_pi_text.sample.json
```

The real SEC smoke payload uses the locally fetched Apple 10-Q event pack:

```bash
uv run python -m packages.harness.cli < examples/harness/sec_10q_validation_payload_from_pi_text.sample.json
```

## Ask Pi to produce a result

```bash
cd /home/neiku/ns100_agent
source /home/neiku/.config/llm_API_keys/keys.env

PI_CODING_AGENT_DIR=/home/neiku/agents/pi/config \
PI_CODING_AGENT_SESSION_DIR=/home/neiku/agents/pi/sessions \
pi --provider deepseek \
  --model deepseek-v4-flash \
  --tools read,grep,find,ls \
  -p "Read examples/harness/investigator_request.sample.json and return only a JSON object matching examples/harness/investigator_result.sample.json. Do not edit files."
```

The returned object is advisory until Super Bear validates it with
`packages.harness.cli`.
