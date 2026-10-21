# Plugin data handling

This describes the native Solaris Dev Shop package built from source release 0.62.
It is technical documentation of the package, not a replacement for the policies
of the host application or services you choose to use.

## Installation and discovery

The package contains skill instructions, local scripts, fixtures and supporting
files. Its manifests do not configure an MCP service or execution hooks. The
OpenCode adapter reads the bundled workflow files and registers their contents
with the host skill catalog. Installing the package does not create a Solaris
cloud account or connect your workspace to a Solaris-operated backend.

The host application, GitHub and the package manager may make their normal
network requests to download or manage the plugin. Their policies and settings
apply to those requests.

## Inputs and execution

The workflows use the files, prompts and commands that you and the host give
them. The host may transmit prompts or file contents to its model/provider under
its own settings and policies. Some workflows can invoke networked tools or
external services when requested and allowed by the host. Review the destination
and permissions for those operations.

Invoked helpers can read local inputs and write reports, logs, journals or
SQLite databases. Some explicit demonstrations start temporary loopback services.
These outputs can include source excerpts, identifiers, financial test inputs or
local paths. The package adds no automatic upload of those outputs to Solaris.

## Storage and control

Local outputs remain where the invoked command writes them. You control their
retention, access, backups and deletion. Removing the plugin does not necessarily
remove reports or databases created by a workflow. The package does not provide
a general encryption or data-erasure guarantee. Host conversation retention and
model-provider processing are separate from these local files.

Use synthetic or redacted inputs for demonstrations. Do not supply private data
unless the host, model/provider and selected tools are appropriate for it.

## Contacting support

Public GitHub issues are public and are hosted by GitHub. If you email support,
you choose which message and attachments to send to Solaris and its email
provider. Do not post credentials, personal data or private source code in public
issues. Contact shehryar@solaristek.com with questions about the package.

The existing [Solaris website privacy policy](https://www.solaristek.com/privacy-policy/)
identifies the publisher and governs the company website. Its stated website
scope should not be read as a promise about a third-party host's model processing.
