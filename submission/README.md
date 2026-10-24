# Submission materials

These materials describe the implemented EZQuote prototype. Supporting documents and external links that have not been supplied are identified below; their completion is not implied by the repository's availability.

## Repository materials

| Material | Files |
| --- | --- |
| Team-provided preliminary proposal, pending final detail corrections | [PDF](SDC2026_LuluMaster_Preliminary.pdf) · [Editable Word](SDC2026_LuluMaster_Preliminary.docx) |
| Repository-based technical tools declaration, unsigned | [PDF](Tech_Tools_Declaration.pdf) · [Source](TECH_TOOLS_DECLARATION.md) |
| Project pitch deck | [PDF](Pitch_Deck_EzQuote.pdf) · [PowerPoint](Pitch_Deck_EzQuote.pptx) |
| Local product demonstration, synthetic data | [MP4 recording](EzQuote_Demo.mp4), 51 seconds; not a Replit proof or YouTube publication. |

The technical declaration distinguishes the rule-based default workflow, optional OpenAI extraction, development assistance and integrations whose real use has not been verified. It does not replace an official signed form if the competition requires one.

## Preliminary proposal review

The supplied proposal identifies Team Lulu Master, contains the team's eligibility and IP declarations, and includes the leader's signature and date of 24 October 2026. These team-supplied statements and the embedded images are preserved. Checkbox fonts were normalized for readable PDF conversion without changing any checked states.

Before the proposal is submitted to the competition:

- Add the missing leader telephone number; the contact field currently contains an email address only.
- Replace the unresolved “QB” provider/model and cloud-host field in section 3.1 with the actual services and their usage status.
- Review section 2.2 as the proposed GenAI design, rather than evidence of the current implementation. The demonstrated workflow uses local rules, catalog matching and historical pricing. An optional OpenAI adapter exists for legacy catalog extraction and is disabled by default; Qwen is not implemented. Replit configuration is prepared, but deployment has not occurred.

The Word source remains editable for these corrections. The PDF is a review copy, not a claim that every submission requirement is complete.

## Outstanding submission items

| Item | Current status |
| --- | --- |
| Final preliminary proposal details | Source and PDF are available above, including the supplied signature, date and declarations. Leader phone and the “QB” provider/host field still need correction; the proposed GenAI wording needs a final consistency review. |
| Replit proof of use (`Replit_Proof_of_Use.pdf`) | Deployment configuration and a [step-by-step guide](../docs/REPLIT.md) are prepared; actual project/run/deployment and Usage or Credits evidence are still required. No hosted Replit use is claimed. |
| Live prototype URL | Pending a verified public URL accessible to reviewers. The current prototype runs locally. |
| YouTube product demonstration | Local MP4 is available above; pending its final playable public or unlisted YouTube URL. |
| RunPod declaration or proof | Team use is unconfirmed. State “Not used” only if confirmed; add proof only if the service was actually used. |

Missing files and URLs are not linked to placeholders. The proposal, service evidence and video must reflect actual team activity and the capabilities demonstrated by the code.

For installation, architecture and the quotation workflow, start with the [project README](../README.md). Current operating instructions and boundaries are in the [user guide](../docs/USER_GUIDE.md), [integrations guide](../docs/INTEGRATIONS.md) and [testing guide](../docs/TESTING.md).
