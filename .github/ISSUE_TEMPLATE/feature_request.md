name: Feature Request
description: Suggest an idea for this project
title: "[Feature] "
labels: ["enhancement"]
body:
  - type: textarea
    id: what
    attributes:
      label: What
      description: What feature or change are you requesting?
    validations:
      required: true
  - type: textarea
    id: why
    attributes:
      label: Why
      description: Why is this needed? What problem does it solve or what value does it add?
    validations:
      required: true
  - type: textarea
    id: how
    attributes:
      label: How
      description: How should it work? Describe the proposed solution or implementation approach
  - type: textarea
    id: alternatives
    attributes:
      label: Alternatives
      description: Any alternative solutions or features you've considered
  - type: textarea
    id: context
    attributes:
      label: Additional Context
      description: Any other context about the feature request