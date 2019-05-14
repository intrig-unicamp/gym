#!/bin/bash

if [ "$EUID" != "0" ]; then
    echo "Sorry dude! You must be root to run this script."
    exit 1
fi

SCRIPT_NAME='Gym Test'
COMMAND=$1
TEST=$2

echo_bold() {
    echo -e "\033[1m${1}\033[0m"
}

kill_process_tree() {
    top=$1
    pid=$2

    children=`ps -o pid --no-headers --ppid ${pid}`

    for child in $children
    do
        kill_process_tree 0 $child
    done

    if [ $top -eq 0 ]; then
        kill -9 $pid &> /dev/null
    fi
}

reset() {
    init=$1;
    if [ $init -eq 1 ]; then
        echo_bold "-> Resetting $SCRIPT_NAME";
    else
        echo_bold "-> Stopping child processes...";
        kill_process_tree 1 $$
    fi

    byobu kill-session -t "gym-test"

    PLAYERPID=`ps -o pid --no-headers -C gym-player`
    MONPID=`ps -o pid --no-headers -C gym-monitor`
    
    if [ -n "$PLAYERPID" ]
    then
        #echo "$PLAYERPID is running"
        kill -9 $PLAYERPID &> /dev/null
    fi
    
    if [ -n "$MONPID" ]
    then
        #echo "$MONPID is running"
        kill -9 $MONPID &> /dev/null
    fi

    if [ -f ./vnf-br.json ]; then
        echo "Cleaning vnf-br.json"
        rm ./vnf-br.json
    fi

    echo "Cleaning logs"
    rm ./logs/*

    echo "Cleaning csv files"
    rm ./csv/*

    mn -c
}


case "$COMMAND" in
    start)

        if [ -z "$TEST" ]
        then 
            echo_bold "Please, define test case: [ 0 | 1 | 2 | 3 ]"
            exit 1
        fi

        case "$TEST" in
            0)
                SOURCE="./layouts/layout-000.json"
            ;;
            1)
                SOURCE="./layouts/layout-001.json"
            ;;
            2)
                SOURCE="./layouts/layout-002.json"
            ;;
            3)
                SOURCE="./layouts/layout-003.json"
            ;;
            *)
                echo_bold "Test case does not exist - options: [ 0 | 1 | 2 | 3 ]"
                exit 1        
            ;;
        esac

        echo_bold "-> Start: $SCRIPT_NAME Layout Case: $SOURCE"

        case "$TEST" in
            0)
                echo_bold "-> Starting Agents"
                byobu new-session -d -s "gym-test" "gym-agent --id agent-1 --url http://127.0.0.1:8985 --debug"
                byobu new-window "gym-agent --id agent-2 --url http://127.0.0.1:8986 --debug"

                sleep 3
                echo_bold "-> Starting Manager"
                byobu new-window "gym-manager --id manager --url http://127.0.0.1:8987 --contacts http://127.0.0.1:8985 http://127.0.0.1:8986 --debug"

                sleep 2
                echo_bold "-> Starting Player"
                byobu new-window "gym-player --id player --url http://172.17.0.1:8990 --contacts http://127.0.0.1:8987 --debug"
                sleep 5
            ;;
            *)
                echo_bold "-> Starting Containernet Plugin"
                byobu new-session -d -s "gym-test" "/usr/bin/python2.7 ./cnet/main.py"

                sleep 2
                echo_bold "-> Starting Player"
                taasplayercmd="gym-player --id 1 --url http://172.17.0.1:8990 --debug"
                nohup ${taasplayercmd} > logs/player.log 2>&1 &
            ;;
        esac

        sleep 2
        echo_bold "-> Deploying Layout"

        curl -s -X POST --header "Content-Type: application/json" -d "$(envsubst < ${SOURCE})" \
        http://172.17.0.1:8990/layout
        echo_bold " -> Ok"

        echo_bold "-> Waiting for Player Reply"
        webtask="/usr/bin/python3 ./webserver.py"
        nohup ${webtask} > logs/web.log 2>&1 &
        WEBPID=$!
        echo_bold "Webserver pid $WEBPID"
        
        ack=true
        while $ack; do
            sleep 2
            if [ -f ./vnf-br.json ]; then
                echo_bold "Received Player Reply"
                ack=false

                if [ -n "$WEBPID" ]
                then
                    echo_bold "Killing webserver pid $WEBPID"
                    kill -9 $WEBPID &> /dev/null
                fi
            fi
        done

        echo_bold "-> Test Finished - Output: ./vnf-br.json"
        echo_bold "-> Run the stop option to clean the test results/logs"
        ;;

    stop)
        echo_bold "-> Stop"
        reset 1
        ;;

    *)
        echo_bold "Usage: $0 [ start | stop ] [ 0 | 1 | 2 | 3 ]"
        echo_bold "=> Start - Run a test case specified."
        echo_bold "=> Stop - Clean logs/results and operations performed by test case"
        echo_bold "# Test Cases:"
        echo_bold " - 0: Simple two-agents VNF-BD exchanging ping traffic in the localhost scope"
        echo_bold " - 1: Uses containernet to run two agents exchanging iperf3/ping traffic via a dummy VNF"
        echo_bold " - 2: Uses containernet to run three agents exchanging iperf3/ping traffic via a dummy VNF, while monitoring it"
        echo_bold " - 3: Uses containernet to run two agents realizing tcpreplay traffic via a Suricata VNF, while monitoring it (externally and internally)"

        exit 1
esac