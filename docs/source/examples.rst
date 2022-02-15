Examples
=========

This page provides a few simple examples on how to use the VIRL :sup:`2`
Client Library::

    from virl2_client import ClientLibrary
    client = ClientLibrary("https://192.168.1.1", "username", "password")

A custom SSL certificate bundle can be passed in `ssl_verify`::

    client = ClientLibrary("https://192.168.1.1", "username", "password", ssl_verify="./cert.pem")

You can pass a certificate using the ``CA_BUNDLE`` environment variable as well.

If no username or password are given then the environment will be checked,
looking for ``VIRL2_USER`` and ``VIRL2_PASS``, respectively. Environment
variables take precedence over those provided in arguments.

It's also possible to pass the URL as an environment variable ``VIRL2_URL``.

Disabling SSL certificate verification (not recommended)::

    client = ClientLibrary("https://192.168.1.1", "username", "password", ssl_verify=False)

Creating a lab with nodes and links
-----------------------------------

This creates a lab, adds two nodes, interfaces and a link between them::

    lab = client.create_lab()

    r1 = lab.create_node("r1", "iosv", 50, 100)
    r1.config = "hostname router1"
    r2 = lab.create_node("r2", "iosv", 50, 200)
    r2.config = "hostname router2"

    # create a link between r1 and r2
    r1_i1 = r1.create_interface()
    r2_i1 = r2.create_interface()
    lab.create_link(r1_i1, r2_i1)

    # alternatively, use this convenience function:
    lab.connect_two_nodes(r1, r2)

    # start the lab
    lab.start()

    # print nodes and interfaces states:
    for node in lab.nodes():
        print(node, node.state, node.cpu_usage)
        for interface in node.interfaces():
            print(interface, interface.readpackets, interface.writepackets)

    lab.stop()

    lab.wipe()

    lab.remove_node(r2)

    lab.remove()

Stopping all the labs
---------------------

This snippet loops over all labs and stops them::

    for lab in client_library.all_labs():
        lab.stop()

Getting all lab names
---------------------

Get a list of all the lab names the user owns::

    all_labs_names = [lab.name for lab in client_library.all_labs()]

Stopping all labs of a User
---------------------------

The following code loops over all labs the user owns, stops the lab,
wipes the lab and then removes the lab from the controller::

    lab_list = client_library.get_lab_list()
    for lab_id in lab_list:
        lab = client_library.join_existing_lab(lab_id)
        lab.stop()
        lab.wipe()
        client_library.remove_lab(lab_id)


Uploading an image disk file
----------------------------

This shows how to upload a local disk file to the controller.
It can then be used with to create a image definition for a
given node type::

    filename = "/Users/username/Desktop/vios-adventerprisek9-m.spa.158-3.m2.qcow2"
    client_library.definitions.upload_image_file(filename, rename="iosv-test.qcow2")


Using the Client Library with Netmiko
-------------------------------------

The following example shows how the VIRL2 client library
can be combined with `Netmiko <https://github.com/ktbyers/netmiko/>`_.

The code shows how to identify a XRv node in a specific lab and how to create
crypto keys which require special handling as the creation is done in exec mode
and is interactive::

    import getpass
    import netmiko

    from virl2_client import ClientLibrary

    LAB_USERNAME = 'cisco'
    LAB_PASSWORD = 'cisco'
    VIRL_CONTROLLER = 'cml2-controller'
    VIRL_USERNAME = input('username: ')
    VIRL_PASSWORD = getpass.getpass('password: ')

    client = ClientLibrary(VIRL_CONTROLLER,
                           VIRL_USERNAME,
                           VIRL_PASSWORD,
                           ssl_verify=False)

    # this assumes that there's exactly one lab with this title
    our_lab = client.find_labs_by_title('my_lab')[0]
    xr_node = our_lab.get_node_by_label('pe2')

    # open the Netmiko connection via the terminal server
    # (SSH to the controller connects to the terminal server)
    c = netmiko.ConnectHandler(device_type='terminal_server',
                               host=VIRL_CONTROLLER,
                               username=VIRL_USERNAME,
                               password=VIRL_PASSWORD)

    # send CR, get a prompt on terminal server
    c.write_channel('\r')

    # open the connection to the console
    c.write_channel(f'open /{our_lab.id}/{xr_node.id}/0\r')

    # router login
    # this makes an assumption that it's required to login
    c.write_channel('\r')
    c.write_channel(LAB_USERNAME + '\r')
    c.write_channel(LAB_PASSWORD + '\r')

    # switch to Cisco XR mode
    netmiko.redispatch(c, device_type='cisco_xr')
    c.find_prompt()

    # get the list of interfaces
    result = c.send_command('show ip int brief')
    print(result)

    # create the keys
    result = c.send_command('crypto key generate rsa',
                            expect_string='How many bits in the modul us \[2048\]\: ')
    print(result)

    # send the key length
    c.write_channel('2048\n')

    # retrieve the result
    result = c.send_command('show crypto key mypubkey rsa')
    print(result)


Licensing the System
--------------------

The following example shows how to apply a license to the system using a token
and retrieve licensing status using the the VIRL2 client library::

    import getpass
    import json
    from virl2_client import ClientLibrary

    VIRL_CONTROLLER = "cml2-controller"
    VIRL_USERNAME = input("username: ")
    VIRL_PASSWORD = getpass.getpass("password: ")
    SL_TOKEN = input("smart license token: ")
    PRODUCT_CONFIG = input("product configuration: ")

    client = ClientLibrary(VIRL_CONTROLLER, VIRL_USERNAME, VIRL_PASSWORD, ssl_verify=False)

    # Get the licensing handle from the client as a property
    licensing = client.licensing

    # Set the product configuration
    licensing.set_product_license(PRODUCT_CONFIG)

    # Setup default license transport (i.e., directly connected to the external
    # Smart License server)
    licensing.set_default_transport()

    # Register with the Smart License server.
    # Wait for registration and authorization to complete.
    result = licensing.register_wait(SL_TOKEN)

    if not result:
        result = licensing.get_reservation_return_code()
        print(
            "ERROR: Failed to register with Smart License server: {}!".format(result)
        )
        exit(1)

    # Get the current registration status.
    # This returns a JSON blob with license status and authorization details.
    status = licensing.status()

    # Get the current list of licensed features.
    # This returns a JSON blob with licensed features.
    features = licensing.features()

    print(json.dumps(status, indent=2))
    print(json.dumps(features, indent=2))


The output for this would look something like the following::


    {
      "registration": {
        "status": "COMPLETED",
        "expires": "2021-06-10 20:17:39",
        "smart_account": "Foo",
        "virtual_account": "Bar",
        "instance_name": "cml-controller.cml.lab",
        "register_time": {
          "succeeded": null,
          "attempted": "2020-06-10 20:22:33",
          "scheduled": null,
          "status": null,
          "failure": "OK",
          "success": "SUCCESS"
        },
        "renew_time": {
          "succeeded": null,
          "attempted": null,
          "scheduled": "2020-12-07 20:22:40",
          "status": null,
          "failure": null,
          "success": "FAILED"
        }
      },
      "authorization": {
        "status": "IN_COMPLIANCE",
        "renew_time": {
          "succeeded": null,
          "attempted": "2020-07-25 16:44:09",
          "scheduled": "2020-08-24 16:44:08",
          "status": "SUCCEEDED",
          "failure": null,
          "success": "SUCCESS"
        },
        "expires": "2020-10-23 16:39:07"
      },
      "features": [
        {
          "name": "CML - Enterprise License",
          "description": "Cisco Modeling Labs - Enterprise License with 20 nodes capacity included",
          "in_use": 1,
          "status": "IN_COMPLIANCE",
          "version": "1.0"
        },
        {
          "name": "CML \u2013 Expansion Nodes",
          "description": "Cisco Modeling Labs - Expansion node capacity for CML Enterprise Servers",
          "in_use": 50,
          "status": "IN_COMPLIANCE",
          "version": "1.0"
        }
      ]
      "reservation_mode": false,
      "transport": {
        "ssms": "https://tools.cisco.com/its/service/oddce/services/DDCEService",
        "proxy": {
          "server": null,
          "port": null
        },
        "default_ssms": "https://tools.cisco.com/its/service/oddce/services/DDCEService"
      },
      "udi": {
        "hostname": "cml2-controller",
        "product_uuid": "00000000-0000-4000-a000-000000000000"
      },
      "product_license": {
        "active": "CML_Personal",
        "is_enterprise": False
      }
    }

    [
      {
        "id": "regid.2019-10.com.cisco.CML_ENT_BASE,1.0_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxx",
        "name": "CML - Enterprise License",
        "description": "Cisco Modeling Labs - Enterprise License with 20 nodes capacity included",
        "in_use": 1,
        "status": "IN_COMPLIANCE",
        "version": "1.0",
        "min": 0,
        "max": 1
      },
      {
        "id": "regid.2019-10.com.cisco.CML_NODE_COUNT,1.0_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxx",
        "name": "CML \u2013 Expansion Nodes",
        "description": "Cisco Modeling Labs - Expansion node capacity for CML Enterprise Servers",
        "in_use": 50,
        "status": "IN_COMPLIANCE",
        "version": "1.0",
        "min": 0,
        "max": 300
      }
    ]


This example can also be found in the ``examples`` directory as ``licensing.py``.


Using Link Conditioning
-----------------------

The next example applies link conditioning to a link identified by the user. It
requires to provide a username, password and a labname. It will then list all
links inside of this lab. The user will then identify a link where the current
link condition will be shown first (or ``{}``, an empty JSON object if there's
none applied). Then the user can enter new values or "None" if the condition
should be removed::

    import getpass
    import re

    from requests.exceptions import HTTPError

    from virl2_client import ClientLibrary

    VIRL_CONTROLLER = "cml2-controller"
    VIRL_USERNAME = input("username: ")
    VIRL_PASSWORD = getpass.getpass("password: ")
    LAB_NAME = input("enter lab name: ")

    client = ClientLibrary(VIRL_CONTROLLER, VIRL_USERNAME, VIRL_PASSWORD, ssl_verify=False)

    # Find the lab by title and join it as long as it's the only
    # lab with that title.
    labs = client.find_labs_by_title(LAB_NAME)

    if not labs or len(labs) != 1:
        print("ERROR: Unable to find a unique lab named {}".format(LAB_NAME))
        exit(1)

    lobj = client.join_existing_lab(labs[0].id)

    if not lobj:
        print("ERROR: Failed to join lab {}".format(LAB_NAME))
        exit(1)

    # Print all links in the lab and ask which link to condition.
    i = 1
    liobjs = []
    for link in lobj.links():
        print(
            "{}. {}[{}] <-> {}[{}]".format(
                i,
                link.interface_a.node.label,
                link.interface_a.label,
                link.interface_b.node.label,
                link.interface_b.label,
            )
        )
        liobjs.append(lobj.get_link_by_interfaces(link.interface_a, link.interface_b))
        i += 1

    print()
    lnum = 0
    while lnum < 1 or lnum > i:
        lnum = input("enter link number to condition (1-{}): ".format(i))
        try:
            lnum = int(lnum)
        except ValueError:
            lnum = 0

    # Print the selected link's current conditioning (if any).
    link = liobjs[lnum-1]
    print("Current condition is {}".format(link.get_condition()))
    # Request the new conditoning for bandwidth, latency, jitter, and loss.
    # Bandwidth is an integer between 0-10000000 kbps
    # Bandwidth of 0 is "no bandwidth restriction"
    # Latency is an integer between 0-10000 ms
    # Jitter is an integer between 0-10000 ms
    # Loss is a float between 0-100%
    new_cond = input(
        "enter new condition in format 'BANDWIDTH, "
        "LATENCY, JITTER, LOSS' or 'None' to disable: "
    )
    # If "None" is provided disable any conditioning on the link.
    if new_cond.lower() == "none":
        link.remove_condition()
        print("Link conditioning has been disabled.")
    else:
        try:
            # Set the current conditioning based on the provided values.
            cond_list = re.split(r"\s*,\s*", new_cond)
            bw = int(cond_list[0])  # Bandwidth is an int
            latency = int(cond_list[1])  # Latency is an int
            jitter = int(cond_list[2])  # Jitter is an int
            loss = float(cond_list[3])  # Loss is a float
            link.set_condition(bw, latency, jitter, loss)
            print("Link conditioning set.")
        except HTTPError as exc:
            print("ERROR: Failed to set link conditioning: {}", format(exc))
            exit(1)

This example can also be found in the ``examples`` directory as ``link_conditioning.py``.
