# Gym

**Notice**: this is a beta release, and during the month of May/2019 this repository is going to be updated with more code, reviews and documentation, stay tuned!

This is a project to bring into reality the ideas designed in VBaaS (VNF Benchmarking-as-a-Service).
The main purpose of this source code is a modular ad-hoc platform for testing VNFs and their respective infrastructure.

Gym is a reference implementation of the ongoing draft in the Benchmarking Methodology Working Group (BMWG) in Internet Engineering Task Force (IETF), named [**Methodology for VNF Benchmarking Automation**](https://datatracker.ietf.org/doc/draft-rosa-bmwg-vnfbench/).

If you want to cite this work, please use:

ROSA, R. V.; BERTOLDO, C.; ROTHENBERG, C. E. [**Take your vnf to the gym: A testing framework for automated nfv performance benchmarking**](https://ieeexplore.ieee.org/document/8030496). IEEE Communications Magazine, v. 55, n. 9, p. 110–117, 2017. ISSN 0163-6804.


Bibtex:

```bibtex
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
```

## Requirements

This guide assumes you have an environment properly setup with:
* Python 3
* Setuptools
* Python Pip3
* Docker

## Installing

All these packages can be installed using the command below.
This command requires root privileges. It installs gym components in the bare metal and creates the raphaelvrosa/gym:0.1 docker image to be used by the test cases.

```bash
$ sudo ./build.sh
```

It will install all the packages and create the docker image that will be
used in the test scenario.

It's also recommended to add your user to the `docker` group:

```bash
$ sudo usermod -a -G docker $USER
```

Then logout and log in back again.

To install Gym for **development** purposes, run:

```bash
$ sudo python3 setup.py develop
```

This will not actually install all the files in your system, but just link them to your development directory, simplifying the code/deploy/test cycle.

### Docker Image

You can also find the gym docker image directly at:
* https://hub.docker.com/r/raphaelvrosa/gym


## Tests

In the folder gym/tests there exists a run.sh file that can trigger the execution of different gym test cases.
To execute any test just type, for instance "sudo -H ./run.sh start 0". And after run, to clean all the test data just run "sudo -H ./run.sh stop".

There are 4 tests enabled by default in the run.sh file. Each one of the tests requires different capabilities, as described below.
For instance, to be able to run tests 1, 2 and 3, you must install:
* Containernet: https://containernet.github.io/

Besides, tests 1, 2 and 3 demand VNF images to be build. Thus:
```bash
$ cd gym/tests/utils
$ sudo ./build_reqs.sh
```

Important: Tests were performed on Ubuntu 18.04.

### Test 0

Performs the execution of two agents just executing ping commands locally on the host machine.

### Test 1

Uses the containernet platform to deploy agents and a dummy VNF, which just bypass the traffic among its ports. The agents perform the execution of ping/iperf3 traffic through the target VNF.

**Notice**: In the tests 1, 2 and 3, the flow of information consists in starting a player component and the containernet platform. When deployed a layout on player, it requires containernet to build the scenario to run the other gym components needed for the test. After the topology is deployed, player reaches manager to get the components status, and starts deploying the tasks. After all tasks are finished, player demands the scenario to be finished in the containernet platform and finally outputs the vnf-br to a json file.

### Test 2

Uses the containernet platform to deploy agents and a dummy VNF, which just bypass the traffic among its ports. The agents perform the execution of ping/iperf3 traffic through the target VNF, while its container is monitored during the test.

Before running Test 2, you need to create the (SUT) VNF bypass docker image, following:
```bash
$ git clone https://github.com/raphaelvrosa/gym-vnfs
$ cd gym-vnfs
$ sudo chmod +x build.sh
$ sudo ./build.sh
```

### Test 3

Uses the containernet platform to deploy agents and a Suricata-IDS VNF. The agents perform the execution of tcpreplay traffic through the target VNF, while its container is monitored externally and the Suricata process is monitored internally in the VNF.
The test consists in executing different pcap files using tcpreplay  while the VNF suricata has loaded different rule sets.
In the end all the metrics are saved into csv files into the gym/tests/csv folder, included the timeseries monitoring of the container, and the overall VNF-PP metrics according to the VNF-BD input parameters. 

Before running Test 3, you need to create the (SUT) Suricata IDS docker image, following:
```bash
$ git clone https://github.com/raphaelvrosa/gym-vnfs
$ cd gym-vnfs
$ sudo chmod +x build.sh
$ sudo ./build.sh
```

In addition, as Test 3 uses pcap files to be sent via tcpreplay by an Agent, you also need to download such pcaps:
```bash
$ wget https://s3.amazonaws.com/tcpreplay-pcap-files/smallFlows.pcap
$ wget https://s3.amazonaws.com/tcpreplay-pcap-files/bigFlows.pcap
$ sudo mkdir /mnt/pcaps/
$ sudo mv bigFlows.pcap /mnt/pcaps/ 
$ sudo mv smallFlows.pcap /mnt/pcaps/ 
```

After that the Agent source of stimulus will be able to mount the /mnt/pcaps/ directory and replay the pcap files for Test 3.
Thus, now the requirements are fulfilled for Test 3 execution.

# License

Gym is released under Apache 2.0 license.

# Contact

If you have any issues, please use GitHub's [issue system](https://github.com/intrig-unicamp/gym/issues) to get in touch.

## Mailing-list

If you have any questions, please use the mailing-list at https://groups.google.com/forum/#!forum/gym-discuss.

## Contribute

Your contributions are very welcome! Please fork the GitHub repository and create a pull request.

## Lead Developer

Raphael Vicente Rosa
* Mail: <raphaelvrosa (at) gmail (dot) com>
* GitHub: [@raphaelvrosa](https://github.com/raphaelvrosa)
* Website: [INTRIG Webpage](https://intrig.dca.fee.unicamp.br/raphaelvrosa/)

This project is part of [**INTRIG (Information & Networking Technologies Research & Innovation Group)**](http://intrig.dca.fee.unicamp.br) at University of Campinas - UNICAMP, Brazil.

INTRIG is led by [**Prof. Dr. Christian Esteve Rothenberg**](https://intrig.dca.fee.unicamp.br/christian/).

# Acknowledgements

This project was supported by Ericsson Innovation Center in Brazil.
