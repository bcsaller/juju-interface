======================================
Interface: Juju formalizing interfaces
======================================
*Webservice for interfaces and their in repo format*
_Interfaces should be easily reused in such a way as to encource smart highly
connected charms. This tooling is to facalitate this._




Key stakeholder(s)
====================
Charm authors
Interface maintainers
charm-tools maintainers
Eventually the charm store maintainers

Lead: Benjamin Saller <benjamin.saller@canonical.com>

| Stakeholder | Approval Date |
| ----------- | ------------- |
|             |               |
|             |               |





User Stories
============
As a new charmer I want easy access to new Juju relations. 
As a charm author I want to be able to take advantage of new features in relations.
As a charm author I want to easily compose relation stubs into my charm.
As an interface creator I want to easily create and publish interface code.
As an interface maintainer I want to publish a new set of changes to my interface.

Assumptions
===========
We will be able to run a webservice to resolve interface: URIs, Over time this
prototype should evolve to be included in the charm store and follow the same
patterns as juju publish.

Risks
===========
As with any central repo (the webservice keeping the interface index) we must
control access to updating the interface code. There are always security risks
with providing access control around a central pool of data. Simple design and
~charmer intervention should allow us to minimize risk in the prototype.

Design Document
===============

 - There should be a webservice maintaining a shared index frontended by a REST
   API. 
 - The webservice should map interface name URIs to endpoints in the REST
   collection which allow selection of an interface stub.
 - CLI tools should use the REST API to publish changes to the index (though
   this maybe deferred through a ~charmer intervention).
 - Charm generate/refresh should be able to resolve interfaces via this service
   and compose them into charms.

Interface URIs
---------------

Interface names should take the form common to charm store styled naming but
using the 'interface' scheme.

interface:mysql  (ambiguous naming)

interface:~bcsaller/mysql

interface:mysql-2


Interface Structure
--------------------
Interface repos should be kept in repositories with the following format
```
<interface base name>/
     interface.yaml
     /provides/...
     /requires/...
     /peer/...
```

interface.yaml will contain metdata about the interface. name, maintainer, category.

An interface must then provide implementations for both requires and provides
in those directories or a single implementation for peer. The format of this is
TBD but will have to define handlers for normal relation events (oined,
changed, etc) and some indication of how to packages deps used in the impl of
the interface such that it can be consumed by the charm.

Milestones
===========
1st pass over on disk format
1st pass over REST API with basic service
Working basic webservice (read-only public api, admin only publish)
1st pass over public HTML interface
charm tools interface to API for list, publish, search

Access control for individual interaces.

Move code into charmstore

Test Plan
==========
How will this project implement testing, and CI if needed.


User Acceptance
================
How we know when this feature is complete
How will stakeholder verify the user stories are complete.

Document
=============
Describe the user workflow and how stakeholders can use the new feature.
Blog about the super awesomeness of incremental deliverables, milestones, and progress

Peer Review
============
Document who reviewed this document and ack’ed should include members of the project as well as members from other anchorships


| Reviewer | Review Date   |
| -------- | ------------- |
|          |               |












