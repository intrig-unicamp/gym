echo "This scripts clones and builds the images needed for the gym test case 1, 2 and 3"
echo "And download pcap files needed for test case 3"

git clone https://github.com/raphaelvrosa/gym-vnfs

cd gym-vnfs

sudo chmod +x build.sh

sudo ./build.sh

echo "Downloading pcap files for test case 3"
wget https://s3.amazonaws.com/tcpreplay-pcap-files/smallFlows.pcap 
wget https://s3.amazonaws.com/tcpreplay-pcap-files/bigFlows.pcap

sudo mkdir -p /mnt/pcaps
sudo mv smallFlows.pcap /mnt/pcaps/
sudo mv bigFlows.pcap /mnt/pcaps/

echo "Added pcap files smallFlows.pcap and bigFlows.pcap to /mnt/pcaps/ folder"


echo "Installing packages to run containernet"

sudo apt install byobu python-pip
sudo pip install psutil gevent requests Flask-RESTful flask

