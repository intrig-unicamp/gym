Architecture View
=================

Agent. Executes active stimulus using extensible interfaces to probers to benchmark and
collect network and system performance metrics. While a single Agent is capable of perform-
ing localized benchmarks in execution environments (e.g., stress tests on CPU, memory, disk
I/O), the interaction among distributed Agents enable the generation and collection of VNF
end-to-end metrics (e.g., frame loss rate, latency). In a benchmarking setup, one Agent can
create the stimuli and the other end be the VNF itself where, for example, one-way latency is
evaluated. An Agent can be defined by a physical or virtual network function. Agents expose
modular APIs for flexible extensibility (e.g., new probers). Agents receive instructions from
a Manager defining sets of actions to consistently configure and run prober instances, parse
the results, and send back snapshots containing output evaluations of the probers’ actions.

Prober – defines a software/hardware-based tool able to generate stimulus traffic
specific to a VNF (e.g., sipp) or generic to multiple VNFs (e.g., pktgen). A prober must
provide programmable interfaces for its life cycle management workflows, e.g., configuration
of operational parameters, execution of stimuli, parsing of extracted metrics, and debugging
options. Specific probers might be developed to abstract and to realize the description of
particular VNF benchmarking methodologies.

Monitor. When possible, it is instantiated inside the target VNF or NFVI PoP (e.g., as
a plug-in process in a virtualized environment) to perform passive monitoring/instrumenta-
tion, using listeners, for metrics collection based on benchmark tests evaluated according to
Agents’ stimuli. Different from the active approach of Agents that can be seen as generic
benchmarking VNFs, Monitors observe particular properties according to NFVI PoPs and
VNFs capabilities. A Monitor can be defined as a virtual network function. Similarly to the
Agent, Monitors interact with the Manager by receiving instructions and replying with snap-
shots. Different from the generic VNF prober approach of the Agent, Monitors may listen to
particular metrics according to capabilities offered by VNFs and their respective execution
environment (e.g. CPU cycles of DPDK-enabled processors).

Listener – defines one or more software interfaces for the extraction of particular
metrics monitored in a target VNF and/or execution environment. A Listener must provide
programmable interfaces for its life cycle management workflows, e.g., configuration of op-
erational parameters, execution of monitoring captures, parsing of extracted metrics, and
debugging options. White-box benchmarking approaches must be carefully analyzed, as var-
ied methods of performance monitoring might be coded as a Listener, possibly impacting the
VNF and/or execution environment performance results.

Manager. Responsible for (i) keeping a coherent state and consistent coordination and
synchronization of Agents and Monitors, their features and activities; (ii) interacting with
the Player to receive tasks and decompose them into a concrete set of instructions; and (iii)
processing snapshots along proper aggregation tasks into reports back to the Player.

Player. Defines a set of user-oriented, north-bound interfaces abstracting the calls needed
to manage, operate, and build a VNF-BR. Player can store different VNF Benchmarking
Descriptors, and trigger their execution when receiving a testing Layout request, that might
reference one or more parametrized VNF-BDs, which are decomposed into a set of tasks or-
chestrated by Managers to obtain their respective reports. Interfaces are provided for storage
options (e.g., database, spreadsheets) and visualization of the extracted reports into VNF-
PPs.