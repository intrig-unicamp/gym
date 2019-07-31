Gym - Under the Hood
====================

After installed, to start any Gym component, just specify an id and url.
E.g.: gym-agent --id 1 --url http://127.0.0.1:8989

So the Agent started above will have an identity "1" and operating in the management interface "http://127.0.0.1:8989" via REST. The field --debug will enable debugging messages of the component. 
Another option to be added to initial operations of an script is the field "--contacts".
This field can specify any list of contacts the component would be able to reach when started. For instance,

	```bash
	$ gym-agent --id 1 --url http://127.0.0.1:8989

	$ gym-agent --id 2 --url http://127.0.0.1:8988
	```

if two agents are started as the commands above, an manager can be started to reach those agents using the following command:


	```bash
	$ gym-manager --id 3 --url http://127.0.0.1:8990 --contacts http://127.0.0.1:8989 http://127.0.0.1:8988
	```
Thus, when started, manager is going to reach the agents via the management urls specified by the contacts field.

	```bash
	$ gym-player --id 4 --url http://127.0.0.1:8991 --contacts http://127.0.0.1:8990
	```

Likewise, a player when started is going to reach the manager component via the specified url by the contacts field.


## Gym Handshake: Hello and Info

When a component reaches another via the specified url(s) by the contacts field, it is going to send a Hello message containing its reachability information. I.e., such message defines the source node following fields: uuid, url, prefix, role.
In the case  a manager component is started with the following command:
gym-manager --id 3 --url http://127.0.0.1:8990 --contacts http://127.0.0.1:8989

It's going to send a message to the contact with url "http://127.0.0.1:8989" specifying it has {uuid:3, url:http://127.0.0.1:8990, prefix: random (e.g., 1998), role: manager}.

The prefix field is going to be randomly generated when the contact is created by the manager component. Such prefix defines that the manager component is always going to reach the other component via that prefix. I.e., using the url "http://127.0.0.1:8989/1988".

When receiving a Hello message, a component is going to create the contact using the information contained in the message. And it is going to reply with an Info message containing the exact information it has about itself (same data as contained in the Hello message). 

Notice: every component must specify a url prefix to reach another component.


Agent/Monitor
Both components load their probers/listeners when started. Each prober/listener is specified by the component source folder. 
E.g., in the source folder (path gym/agent/probers) each file named prober_* (e.g., prober_ping.py). Similarly, the same applies for the monitor component and its listeners. 
Each prober/listerner contains an unique identifier, its execution parameters and its output metrics. 
This way, an Agent/Monitor will have all its operational features (i.e., probers/listeners available for tests) and envrionmental features (i.e., information regarding the allocated resources for the component, such as cpu, memory, disk, operating system version). 


Manager
It realizes the discovery of features from and the coordination activities of Agents/Monitors. 
Therefore, it waits for contacts from Agents/Monitors or Player components.
 

Player
Players starts with contacts specified, reaching then a Manager component, which reaches all the "subcontacts" specified by Player, if not yet already reached. Thus Player detains the whole information of Manager and its incumbent Agent(s)/Monitor(s).


Messaging
Messages are all exchanged in the JSON format, in an RPC-like format.
Future work consists in evolvint the messaging system to an actual RPC system through well-known frameworks (e.g., gRPC) or even utilize distributed storage/streamming platforms (e.g., etcd, kafka, zeromq).  

REST-(like) APIs are simply defined by POST, so not yet full REST. Ideally, Gym components will evolve to have full REST APIs, together with streamming platforms, optional for users determine their needs.

Storage
Gym aims to support different storage options of its output results (VNF-BRs) in the Player component. Currently gym supports storage in disk and in the elasticsearch database.


Debugging
Providing the option --debug when starting any gym component, all the debug messages are shown in the terminal. 
Later, gym aims to create granular debugging methods for its components.