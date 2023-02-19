---
title: Events
nav_order: 10
---

# Events

The attribute `ha_event` shows whether the event is triggered by an HA initiated action

##  Calendar Events

Events will be raised for the following items.

- o365_create_calendar_event - Creation of a new event via the O365 integration
- o365_modify_calendar_event - Update of an event via the O365 integration
- o365_remove_calendar_event - Removal of an event via the O365 integration
- o365_respond_calendar_event - Response to an event via the O365 integration

The events have the following general structure:

```yaml
event_type: o365_create_calendar_event
data:
  event_id: >-
    AAMkAGQwYzQ5ZjZjLTQyYmItNDJmNy04NDNjLTJjYWY3NzMyMDBmYwBGAAAAAAC9VxHxYFrdCHSJkXtJ-BwCoiRErLbiNRJDCFyMjq4khAAY9v0_vAACoiRErLbiNRJDCFyMjq4khAAcZSY4SAAA=
  ha_event: true
origin: LOCAL
time_fired: "2023-02-19T15:29:01.962020+00:00"
context:
  id: 01GSN4NWGABVFQQWPP2D8G3CN8
  parent_id: null
  user_id: null
```

##  Task Events

Events will be raised for the following items.

- o365_new_task - New task created either by the O365 integration or via some external app
- o365_update_task - Update of a task via the O365 integration
- o365_delete_task - Deletion of a task via the O365 integration
- o365_completed_task - Task marked complete via some external app

It should be noted that actions occurring external to HA are identified via a 30-second poll, so will very likely be delayed by up to that time. Any new task or completed task occurring within 5 minutes before HA restart will very likely have a new event sent after the restart.

The events have the following general structure. A `created` or `completed` attribute will be included where the action happened outside HA:

```yaml
event_type: o365_new_task
data:
  task_id: >-
    AAMkAGQwYzQ5ZjZjLTQyYmItNDJmNy04NDNjLTJjYWY3NzMyMDBGAAAAAAC9VxHxYFTdSrdCHSJkXtJ-BwCoiRErLbiNRJDCFyMjq4khAAbWN3xqAACoiRErLbiNRJDCFyMjq4khAAcZSXKvAAA=
  created: "2023-02-19T15:36:05.436266+00:00"
  ha_event: false
origin: LOCAL
time_fired: "2023-02-19T15:36:14.679300+00:00"
context:
  id: 01GSN5332Q90ZKVEX0CZQNND73
  parent_id: null
  user_id: null
```