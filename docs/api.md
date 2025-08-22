# API Endpoints

This document describes the lightweight demonstration endpoints exposed by the
application server.

## `POST /import_stories`

Import a list of stories into an in-memory store.

```json
[
  {"id": "story1", "events": ["filed", "heard"]}
]
```

Response

```json
{"imported": 1}
```

## `POST /check_event`

Check whether a given story contains a specific event.

```json
{"story_id": "story1", "event": "filed"}
```

Response

```json
{"event_present": true}
```

## `POST /rules`

Extract normative rules from free-form text.

```json
{"text": "A person must not litter in public places."}
```

Response

```json
{
  "rules": [
    {
      "actor": "A person",
      "modality": "must not",
      "action": "litter in public places",
      "conditions": null,
      "scope": null
    }
  ]
}
```
