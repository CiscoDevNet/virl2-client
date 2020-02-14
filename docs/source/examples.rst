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

Creating a lab with nodes and links::

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





Stopping all the labs::

    for lab in client_library.all_labs():
        lab.stop()

Getting all lab names::

    all_labs_names = [lab.name for lab in client_library.all_labs()]

A way to remove all the labs on the server is::

    lab_list = client_library.get_lab_list()
    for lab_id in lab_list:
        lab = client_library.join_existing_lab(lab_id)
        lab.stop()
        lab.wipe()
        client_library.remove_lab(lab_id)


Uploading an image disk file::

    filename = "/Users/username/Desktop/vios-adventerprisek9-m.spa.158-3.m2.qcow2"
    client_library.definitions.upload_image_file(filename, rename="iosv-test.qcow2")


