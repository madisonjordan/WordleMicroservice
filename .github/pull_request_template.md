## PR Checklist

#### Tests

- [ ] tested services
  - [ ] functions working for this feature
  - [ ] autodocumentation works
- [ ] tested configuration
  - [ ] launches services
  - [ ] reverse proxy
  - [ ] load balancing
  - [ ] runs cron job

#### Design Requirements

- [ ] input/output representations in json format
- [ ] BFF service doesn't access database (SQL or Redis)
- [ ] maintains statelessness (independent services)
  - [ ] separate python files for each service
  - [ ] Answer Service doesn't store current day's answer on the server side
  - [ ] Answer Service doesn't track number of guesses made by a client

#### Readability / Maintainability

- [ ] commented code
- [ ] follows PEP8 style / passes linting checks

## Description

Closes #...

#### Changes

-
