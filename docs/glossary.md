# Glossary

- **Attempt:** One bounded implementation or correction cycle for a DAG node. The first attempt counts toward the five-attempt limit.
- **DAG:** A directed acyclic graph of tasks where each dependency must be accepted before dependent work becomes ready.
- **Evidence:** A record of an observed command result and artifact hashes tied to a node snapshot.
- **Logical role:** Provider-neutral responsibility such as orchestrator, implementer, complex implementer, or reviewer.
- **Node snapshot:** A hash of the plan header, the node and dependency definitions, and their input hashes.
- **READY frontier:** The lexically ordered set of tasks whose dependencies are accepted.
- **Runtime qualification:** A check performed in the actual client environment. Static metadata validation alone is not runtime qualification.
- **Deferred external obligation:** A required check that needs an external application or infrastructure not exercised yet.
