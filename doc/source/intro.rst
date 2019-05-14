
************************************************
Gym
************************************************

Gym is a reference implementation of the ongoing draft in the Benchmarking Methodology Working Group (BMWG) in Internet Engineering Task Force (IETF), named https://datatracker.ietf.org/doc/draft-rosa-bmwg-vnfbench/ 

If you want to cite this work, please use:

ROSA, R. V.; BERTOLDO, C.; ROTHENBERG, C. E. [**Take your vnf to the gym: A testing framework for automated nfv performance benchmarking**](https://ieeexplore.ieee.org/document/8030496). IEEE Communications Magazine, v. 55, n. 9, p. 110–117, 2017. ISSN 0163-6804.

Bibtex:

@ARTICLE{Rosa:2017:Gym,
author={R. V. {Rosa} and C. {Bertoldo} and C. E. {Rothenberg}},
journal={IEEE Communications Magazine},
title={Take Your VNF to the Gym: A Testing Framework for Automated NFV Performance Benchmarking},
year={2017},
volume={55},
number={9},
pages={110-117},
keywords={program testing;virtualisation;VNF;automated NFV performance benchmarking;software entity;testing framework;vIMS scenario;network functions virtualization;Benchmark testing;Measurement;Monitoring;Software testing;Visualization;Network function virtualization},
doi={10.1109/MCOM.2017.1700127},
ISSN={0163-6804},
month={Sep.},
}


Gym was built to receive high-level test descriptors and execute them
to extract VNFs profiles, containing measurements of performance
metrics - especially to associate resources allocation (e.g., vCPU)
with packet processing metrics (e.g., throughput) of VNFs.  From the
original research ideas, such output profiles might be used
by orchestrator functions to perform VNF lifecycle tasks (e.g.,
deployment, maintenance, tear-down).

The proposed guiding principles to design
and build Gym can be composed in multiple practical ways for
different VNF testing purposes:

* Comparability: Output of tests shall be simple to understand and
    process, in a human-read able format, coherent, and easily
    reusable (e.g., inputs for analytic applications).

* Repeatability: Test setup shall be comprehensively defined through
    a flexible design model that can be interpreted and executed by
    the testing platform repeatedly but supporting customization.

* Configurability: Open interfaces and extensible messaging models
    shall be available between components for flexible composition of
    test descriptors and platform configurations.

* Interoperability: Tests shall be ported to different environments
    using lightweight components.


