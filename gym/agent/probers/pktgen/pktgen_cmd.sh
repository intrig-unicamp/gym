#!/bin/bash
#
# Simple example:
#  * pktgen sending with single thread and single interface
#  * flow variation via random UDP source port
#
# Adapter from: https://github.com/torvalds/linux/blob/master/samples/pktgen/pktgen_sample01_simple.sh


basedir=`dirname $0`
source ${basedir}/parameters.sh
source ${basedir}/functions.sh
root_check_run_with_sudo "$@"

# Parameter parsing via include
# - go look in parameters.sh to see which setting are avail
# - required param is the interface "-i" stored in $DEV
#
# Set some default params, if they didn't get set
if [ -z "$DEST_IP" ]; then
    [ -z "$IP6" ] && DEST_IP="198.18.0.42" || DEST_IP="FD00::1"
fi
[ -z "$CLONE_SKB" ] && CLONE_SKB="0"
# Example enforce param "-m" for dst_mac
#[ -z "$DST_MAC" ] && usage && err 2 "Must specify -m dst_mac"
[ -z "$DURATION" ] && DURATION=10

# Base Config
DELAY="0"        # Zero means max speed
COUNT="0"   # Zero means indefinitely

# Flow variation random source port between min and max
UDP_MIN=9
UDP_MAX=9

# General cleanup everything since last run
# (especially important if other threads were configured by other scripts)
pg_ctrl "reset"

# Add remove all other devices and add_device $DEV to thread 0
thread=0
pg_thread $thread "rem_device_all"
pg_thread $thread "add_device" $DEV

# How many packets to send (zero means indefinitely)
pg_set $DEV "count $COUNT"


# Reduce alloc cost by sending same SKB many times
# - this obviously affects the randomness within the packet
pg_set $DEV "clone_skb $CLONE_SKB"

if [ -n "$RATEB" ]; then
    # Set rate bps
    pg_set $DEV "rate $RATEB"
fi


if [ -n "$RATEP" ]; then
    # Set rate pps
    pg_set $DEV "ratep $RATEP"
fi

# Set packet size
pg_set $DEV "pkt_size $PKT_SIZE"

# Delay between packets (zero means max speed)
pg_set $DEV "delay $DELAY"

# Flag example disabling timestamping
# pg_set $DEV "flag NO_TIMESTAMP"

# Source
if [ -n "$SRC_MAC" ]; then
    pg_set $DEV "src_mac $SRC_MAC"
fi

if [ -n "$SRC_IP" ]; then
    pg_set $DEV "src_min $SRC_IP"
    pg_set $DEV "src_max $SRC_IP"
fi

# Destination
if [ -n "$DST_MAC" ]; then
    pg_set $DEV "dst_mac $DST_MAC"
fi

if [ -n "$DEST_IP" ]; then
    pg_set $DEV "dst_min $DEST_IP"
    pg_set $DEV "dst_max $DEST_IP"
fi

# Setup random UDP port src range
# pg_set $DEV "flag UDPSRC_RND"
# pg_set $DEV "udp_src_min $UDP_MIN"
# pg_set $DEV "udp_src_max $UDP_MAX"

pgrun()
{
    # start_run
    pg_ctrl "start"
}

run_test()
{
    # echo "Running... ctrl^C to stop" >&2
    pgrun &
    pid=$!

    sleep $DURATION
    # pg_ctrl "stop"
    kill -INT $pid
    # echo "Done" >&2
    wait; sleep 1
}

output_json()
{
    sent=$(awk '/^Result:/{print $5}' <$PGDEV)
    pps=$(awk 'match($0,/'\([0-9]+\)pps'/, a) {print a[1]}' <$PGDEV)
    bps=$(awk 'match($0,/'\([0-9]+\)bps'/, a) {print a[1]}' <$PGDEV)
    mbps=$(awk 'match($0,/'\([0-9]+\)Mb'/, a) {print a[1]}' <$PGDEV)
    errors=$(awk '/errors:/{print $5}' <$PGDEV)
    echo { '"packets_sent"':$sent , '"packets_per_second"':$pps, '"bits_per_second"':$bps, '"megabits_per_second"':$mbps, '"errors"':$errors }
}

run_test >/dev/null

# Print results
# echo "Result device: $DEV"
PGDEV=/proc/net/pktgen/$DEV
# cat /proc/net/pktgen/$DEV
output_json
