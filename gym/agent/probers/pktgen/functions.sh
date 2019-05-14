#
# Common parameter parsing for pktgen scripts
#
# Extracted from: https://github.com/torvalds/linux/tree/master/samples/pktgen

function usage() {
    echo ""
    echo "Usage: $0 [-vx] -i ethX"
    echo "  -y : (\$DURATION)  duration"
    echo "  -i : (\$DEV)       output interface/device (required)"
    echo "  -z : (\$PKT_SIZE)  packet size"
    echo "  -d : (\$DEST_IP)   destination IP"
    echo "  -m : (\$DST_MAC)   destination MAC-addr"
    echo "  -s : (\$SRC_IP)   source IP"
    echo "  -a : (\$SRC_MAC)   source MAC-addr"
    echo "  -r : (\$RATE)   rate bps"
    echo "  -p : (\$RATEP)   rate pps"
    echo "  -t : (\$THREADS)   threads to start"
    echo "  -c : (\$SKB_CLONE) SKB clones send before alloc new SKB"
    echo "  -b : (\$BURST)     HW level bursting of SKBs"
    echo "  -v : (\$VERBOSE)   verbose"
    echo "  -x : (\$DEBUG)     debug"
    echo "  -6 : (\$IP6)       IPv6"
    echo ""
}

##  --- Parse command line arguments / parameters ---
## echo "Commandline options:"
while getopts "y:z:i:d:m:s:a:r:p:t:c:b:vxh6" option; do
    case $option in
        y) # duration
          export DURATION=$OPTARG
	#   echo "Duration set to: DURATION=$DURATION"
          ;;

        i) # interface
          export DEV=$OPTARG
	#   echo "Output device set to: DEV=$DEV"
          ;;
        z)
          export PKT_SIZE=$OPTARG
	#   echo "Packet size set to: PKT_SIZE=$PKT_SIZE bytes"
          ;;
        d) # destination IP
          export DEST_IP=$OPTARG
	#   echo "Destination IP set to: DEST_IP=$DEST_IP"
          ;;
        m) # destination MAC
          export DST_MAC=$OPTARG
	#   echo "Destination MAC set to: DST_MAC=$DST_MAC"
          ;;
        s) # source IP
        export SRC_IP=$OPTARG
 #  	  echo "Source IP set to: SRC_IP=$SRC_IP"
          ;;
        a) # source MAC
        export SRC_MAC=$OPTARG
 #  	  echo "Source MAC set to: SRC_MAC=$SRC_MAC"
          ;;
        r) # rate bps
        export RATEB=$OPTARG
 #  	  echo "Rate bps set to: RATE=$RATEB"
          ;;
        p) # rate pps
        export RATEP=$OPTARG
 #  	  echo "Rate pps set to: RATEP=$RATEP"
          ;;
        t)
	    export THREADS=$OPTARG
        export CPU_THREADS=$OPTARG
	    let "CPU_THREADS -= 1"
	#   echo "Number of threads to start: $THREADS (0 to $CPU_THREADS)"
          ;;
        c)
	       export CLONE_SKB=$OPTARG
	#   echo "CLONE_SKB=$CLONE_SKB"
          ;;
        b)
	       export BURST=$OPTARG
	#   echo "SKB bursting: BURST=$BURST"
          ;;
        v)
          export VERBOSE=yes
        #   echo "Verbose mode: VERBOSE=$VERBOSE"
          ;;
        x)
          export DEBUG=yes
        #   echo "Debug mode: DEBUG=$DEBUG"
          ;;
	    6)
	      export IP6=6
        #   echo "IP6: IP6=$IP6"
          ;;
        h|?|*)
          usage;
          echo "[ERROR] Unknown parameters!!!"
          exit 2
    esac
done
shift $(( $OPTIND - 1 ))

if [ -z "$PKT_SIZE" ]; then
    # NIC adds 4 bytes CRC
    export PKT_SIZE=60
    # echo "Default packet size set to: set to: $PKT_SIZE bytes"
fi

if [ -z "$THREADS" ]; then
    # Zero CPU threads means one thread, because CPU numbers are zero indexed
    export CPU_THREADS=0
    export THREADS=1
fi

if [ -z "$DEV" ]; then
    usage
    echo  "Please specify output device"
    exit 2
fi

if [ -z "$DEST_IP" ]; then
    echo "Missing destination IP address"
    exit 2
fi

if [ ! -d /proc/net/pktgen ]; then
    echo "Loading kernel module: pktgen"
    modprobe pktgen
fi
