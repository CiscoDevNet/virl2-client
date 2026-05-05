.. virl2_client documentation master file, created by

CML 2 API Client Documentation
==============================

This is the CML 2 client library (`virl2_client`). It provides a Python package
to programmatically create, edit, delete and control network simulations on a
CML 2 controller.

.. toctree::
    :maxdepth: 2
    :caption: Content
    :glob:

    intro
    examples
    api/*

.. only:: internal

    .. _download:

    Download
    --------

    `Download the client library (Linux/Win/macOS) </client/virl2_client.whl>`_

    You can also download the client library directly from a terminal using the
    permanent link below. Replace ``<controller>`` with the address of your CML2
    controller. Use ``curl`` with ``--remote-header-name`` (short option ``-J``)
    so that the file name from the server's ``Content-Disposition`` header is
    preserved::

        curl -kLO --remote-header-name https://<controller>/client/virl2_client.whl

    .. note::
        Preserving the original file name is important: ``pip`` relies on the
        wheel's file name to determine the distribution name, version, Python
        compatibility tag, ABI tag and platform tag (e.g.
        ``virl2_client-2.9.0-py3-none-any.whl``). The permanent URL above ends
        in ``virl2_client.whl`` for convenience, but the server returns the
        fully qualified wheel name via the ``Content-Disposition`` header.
        Without ``--remote-header-name`` the file would be saved as
        ``virl2_client.whl`` and ``pip install`` would reject it as an invalid
        wheel name.

    .. note::
        The ``-k`` (``--insecure``) flag in the ``curl`` command above disables
        TLS certificate verification. It is shown here because a freshly
        installed CML 2 controller uses a self-signed certificate by default.
        Drop ``-k`` once your controller is configured with a CA-issued
        certificate so the download is properly authenticated.

    The client library is distributed under the
    `Apache License, Version 2.0 </client/LICENSE>`_.

    .. note::
        That the above links *only* work when the documentation is viewed
        on the CML 2 controller.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
