FROM ubuntu:18.04

RUN apt update \
	&& apt install -y tcpdump net-tools python3-dev python3-pip libpcap-dev build-essential wget \
					inetutils-ping iperf3 build-essential bc libpcap-dev iperf iproute2

RUN cp /usr/bin/iperf /usr/sbin/iperf

RUN wget -c "https://downloads.sourceforge.net/project/tcpreplay/tcpreplay/4.2.6/tcpreplay-4.2.6.tar.gz?r=https%3A%2F%2Fsourceforge.net%2Fprojects%2Ftcpreplay%2F&ts=1495545608&use_mirror=excellmedia" -O "tcpreplay_426.tar.gz"
RUN tar xzf tcpreplay_426.tar.gz && cd tcpreplay-4.2.6/ && ./configure && make && make install && cd -

RUN pip3 install asyncio aiohttp psutil PyYAML elasticsearch pandas seaborn jinja2 elasticsearch

RUN mkdir -p gym/gym
COPY * /gym/
COPY gym /gym/gym/

RUN cd /gym && python3 setup.py install && cd -
RUN export PATH=$PATH:~/.local/bin

COPY gym/etc/ /etc/gym/