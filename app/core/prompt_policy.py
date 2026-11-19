"""Shared instructions for local evidence interpretation, versioned for evaluation."""

VERSION = "engineering-grounding/1"
GROUNDING = (
    "Scope each observation to its recorded asset, time and source origin. "
    "An unlinked photo is a visual observation only. A prior case supplies a comparison, "
    "not evidence that this asset has the same fault. If records disagree, attribute each "
    "account and leave the conflict unresolved. A missing channel has no measured value. "
    "Distinguish chronological endpoints from window averages. Use calculated quantities "
    "only with their supplied units and scope. For a tentative mechanism, explain how it "
    "could produce the observed change and identify a check that could distinguish alternatives."
)
