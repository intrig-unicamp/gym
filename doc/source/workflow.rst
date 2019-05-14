Gym core components communicate through a flexible REpresentational State Transfer
 (REST) Application Programming Interface (API) using generic RPC calls with custom/extensible
 JavaScript Object Notation (JSON) message formats. In the following, we
describe a generic workflow based on request-reply message exchanges and pairwise component
 interactions represented as numbered (1 to 7).

1. The first step consists of a user defining the composition of the VNF testing VNF-BD
containing the structural and functional requirements to express target performance
metrics to generate a VNF-PP.

2. The Player processes the parametrized VNF-BD considering the features offered by
the associated Manager(s). The output is a workflow of tasks, in sequence or parallel,
submitted to a selected Manager that satisfies (i.e. controls a matching set of Agents/-
Monitors) the VNF-BD requirements. Based on input variables, a VNF-BD can be
decomposed into different sets of tasks with the corresponding high-level probers/lis-
teners parameters.

3. The Manager decomposes tasks into a coherent sequence of instructions to be sent to
Agents and/or Monitors. Inside each instruction, sets of actions define parametrized
execution procedures of probers/listeners. Sequential or parallel tasks may include prop-
erties to be decomposed into different sets of instructions, for instance, when sampling
cycles might define their repeated execution.

4. By interpreting action into a prober/listener execution, an Agent or Monitor performs
an active or passive measurement to output metrics via a pluggable tool. A VNF
developer can freely create a customized prober or listener to interface her tests and
extract particular metrics. An interface of such a tool is automatically discovered by
an Agent/Monitor and exposed as available to Managers and Players along with its
corresponding execution parameters and output metrics.

5. After computing the required metrics, a set of evaluations (i.e., parsed action outputs)
integrate a so-called snapshot sent from an Agent/Monitor to the Manager. A snap-
shot associated to a specific task is received from the Agent/Monitor that received
the corresponding instruction. An evaluation contains timestamps and identifiers of
the originating prober/listener, whereas a snapshot receives an Agent/Monitor unique
identifier along the host name information from where it was extracted.

6. After processing all the instructions related tree of snapshots, the Manager composes
a report, as a reply to each task requested by the Player. The Manager can sample
snapshots in a diverse set of programmable methods. For instance, a task may require
cycles of repetition, so the correspondent snapshots can be parsed and aggregated in a
report through statistical operations (e.g., mean, variance, confidence intervals).

7. Finally, the Player processes the report following the VNF-PP metrics definition, as
established initially during the VNF-BD decomposition. While the VNF-PP contains
filtered evaluation metrics and parameters, snapshots can be aggregated/sampled into
a report. Results can be exported in different file formats (e.g., formats CSV, JSON,
YAML) or saved into a database for further analysis and visualization. For instance,
in our current Gym prototype we integrate two popular open source components, the
Elasticsearch database and the Kibana visualization platform 2 —tools providing high
flexibility in querying, filtering and creation of different visual representations of the
extracted VNF-PPs.