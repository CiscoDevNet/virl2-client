Examples
=========

This page provides a few simple examples on how to use the VIRL :sup:`2`
Client Library::

    from virl2_client import ClientLibrary
    client = ClientLibrary("https://192.168.1.1", "username", "password")
    client.wait_for_lld_connected()

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
    VIRL_CONTROLLER = 'virl2-controller'
    VIRL_USERNAME = input('username: ')
    VIRL_PASSWORD = getpass.getpass('password: ')

    client = ClientLibrary(VIRL_CONTROLLER,
                           VIRL_USERNAME,
                           VIRL_PASSWORD,
                           ssl_verify=False)
    client.wait_for_lld_connected()

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
