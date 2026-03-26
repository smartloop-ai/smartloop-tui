name: Bug Report
description: Create a report to help us improve
title: "[Bug] "
labels: ["bug"]
body:
  - type: textarea
    id: what
    attributes:
      label: What
      description: What happened? Describe the bug clearly and concisely
    validations:
      required: true
  - type: textarea
    id: why
    attributes:
      label: Why
      description: Why is this a problem? What impact does it have?
  - type: textarea
    id: how
    attributes:
      label: How
      description: How can we reproduce the issue? Include steps if applicable
    validations:
      required: true
  - type: input
    id: version
    attributes:
      label: Version
      description: Version of smartloop you are using
      placeholder: "slp --version output"
  - type: textarea
    id: logs
    attributes:
      label: Relevant Logs
      description: Any relevant error logs or output
  - type: dropdown
    id: os
    attributes:
      label: OS
      options: ["Linux", "macOS", "Windows", "Other"]