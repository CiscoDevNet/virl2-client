# Changes

Lists the changes in the package as they relate to controller API changes
or functional changes in the package API.  This was started with 2.4.1.

## Version 2.4.1

### import_lab()

This PCL function imports an existing topology from a string.  With the new
schema and the use of UUIDs which was introduced in 2.3, the export format of
labs has also changed:

- interfaces are now stored with the nodes and not in a global list anymore
- specific attributes of nodes/interfaces are not stored in a "data" dictionary
  anymore but with the node/interface itself

Importing / exporting such a lab will use the new representation.  Going
forward, the backward compatibility will be removed with 2.5.  At the moment,
deprecation warnings will be printed in these cases.
