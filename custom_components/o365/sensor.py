"""Sensor processing."""
import datetime
import functools as ft
import logging
from operator import itemgetter

import voluptuous as vol
from homeassistant.const import CONF_ENABLED, CONF_NAME
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity import Entity, async_generate_entity_id
from homeassistant.helpers.update_coordinator import (  # UpdateFailed,
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util import dt
from requests.exceptions import HTTPError

from .const import (
    ATTR_ALL_TASKS,
    ATTR_ATTRIBUTES,
    ATTR_CHAT_ID,
    ATTR_CONTENT,
    ATTR_DUE,
    ATTR_ERROR,
    ATTR_FROM_DISPLAY_NAME,
    ATTR_IMPORTANCE,
    ATTR_OVERDUE_TASKS,
    ATTR_STATE,
    ATTR_SUBJECT,
    ATTR_SUMMARY,
    ATTR_TASKS,
    CONF_ACCOUNT,
    CONF_ACCOUNT_NAME,
    CONF_BODY_CONTAINS,
    CONF_CHAT_SENSORS,
    CONF_DOWNLOAD_ATTACHMENTS,
    CONF_EMAIL_SENSORS,
    CONF_ENABLE_UPDATE,
    CONF_HAS_ATTACHMENT,
    CONF_IMPORTANCE,
    CONF_IS_UNREAD,
    CONF_MAIL_FOLDER,
    CONF_MAIL_FROM,
    CONF_MAX_ITEMS,
    CONF_QUERY_SENSORS,
    CONF_STATUS_SENSORS,
    CONF_SUBJECT_CONTAINS,
    CONF_SUBJECT_IS,
    CONF_TASK_LIST_ID,
    CONF_TODO_SENSORS,
    CONF_TRACK,
    CONF_TRACK_NEW,
    DOMAIN,
    SENSOR_ENTITY_ID_FORMAT,
    SENSOR_MAIL,
    SENSOR_TEAMS_CHAT,
    SENSOR_TEAMS_STATUS,
    SENSOR_TODO,
    YAML_TASK_LISTS,
)
from .schema import NEW_TASK_SCHEMA, TASK_LIST_SCHEMA
from .utils import (
    build_config_file_path,
    build_yaml_filename,
    get_email_attributes,
    load_yaml_file,
    update_task_list_file,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass, config, async_add_entities, discovery_info=None
):  # pylint: disable=unused-argument
    """O365 platform definition."""
    if discovery_info is None:
        return None

    account_name = discovery_info[CONF_ACCOUNT_NAME]
    conf = hass.data[DOMAIN][account_name]
    account = conf[CONF_ACCOUNT]

    is_authenticated = account.is_authenticated
    if not is_authenticated:
        return False

    coordinator = O365SensorCordinator(hass, conf)
    entities = await coordinator.async_setup_entries(hass)
    await coordinator.async_config_entry_first_refresh()
    async_add_entities(entities, False)

    return True


class O365SensorCordinator(DataUpdateCoordinator):
    """O365 sensor data update coordinator."""

    def __init__(self, hass, config):
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="My sensor",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=datetime.timedelta(seconds=30),
        )
        self._config = config
        self._account = config[CONF_ACCOUNT]
        self._account_name = config[CONF_ACCOUNT_NAME]
        self._entities = []
        self._data = {}

    async def async_setup_entries(self, hass):
        """Do the initial setup of the entities."""
        email_entities = await self._async_email_sensors(hass)
        query_entities = await self._async_query_sensors(hass)
        status_entities = self._status_sensors(hass)
        chat_entities = self._chat_sensors(hass)
        todo_entities = await self._async_todo_sensors(hass)
        self._entities = (
            email_entities
            + query_entities
            + status_entities
            + chat_entities
            + todo_entities
        )
        return self._entities

    async def _async_email_sensors(self, hass):
        email_sensors = self._config.get(CONF_EMAIL_SENSORS, [])
        entities = []
        _LOGGER.debug("Email sensor setup: %s ", self._account_name)
        for sensor_conf in email_sensors:
            name = sensor_conf[CONF_NAME]
            _LOGGER.debug(
                "Email sensor setup: %s, %s",
                self._account_name,
                name,
            )
            if mail_folder := await hass.async_add_executor_job(
                _get_mail_folder, self._account, sensor_conf, CONF_EMAIL_SENSORS
            ):
                entity_id = async_generate_entity_id(
                    SENSOR_ENTITY_ID_FORMAT,
                    name,
                    hass=hass,
                )
                emailsensor = O365EmailSensor(
                    self, sensor_conf, mail_folder, name, entity_id
                )
                _LOGGER.debug(
                    "Email sensor added: %s, %s",
                    self._account_name,
                    name,
                )
                entities.append(emailsensor)
        return entities

    async def _async_query_sensors(self, hass):
        query_sensors = self._config.get(CONF_QUERY_SENSORS, [])
        entities = []
        for sensor_conf in query_sensors:
            if mail_folder := await hass.async_add_executor_job(
                _get_mail_folder, self._account, sensor_conf, CONF_QUERY_SENSORS
            ):
                name = sensor_conf.get(CONF_NAME)
                entity_id = async_generate_entity_id(
                    SENSOR_ENTITY_ID_FORMAT,
                    name,
                    hass=hass,
                )
                querysensor = O365QuerySensor(
                    self, sensor_conf, mail_folder, name, entity_id
                )
                entities.append(querysensor)
        return entities

    def _status_sensors(self, hass):
        status_sensors = self._config.get(CONF_STATUS_SENSORS, [])
        entities = []
        for sensor_conf in status_sensors:
            name = sensor_conf.get(CONF_NAME)
            entity_id = async_generate_entity_id(
                SENSOR_ENTITY_ID_FORMAT,
                name,
                hass=hass,
            )
            teams_status_sensor = O365TeamsStatusSensor(
                self,
                self._account,
                name,
                entity_id,
            )
            entities.append(teams_status_sensor)
        return entities

    def _chat_sensors(self, hass):
        chat_sensors = self._config.get(CONF_CHAT_SENSORS, [])
        entities = []
        for sensor_conf in chat_sensors:
            name = sensor_conf.get(CONF_NAME)
            entity_id = async_generate_entity_id(
                SENSOR_ENTITY_ID_FORMAT,
                name,
                hass=hass,
            )
            teams_chat_sensor = O365TeamsChatSensor(
                self, self._account, name, entity_id
            )
            entities.append(teams_chat_sensor)
        return entities

    async def _async_todo_sensors(self, hass):
        todo_sensors = self._config.get(CONF_TODO_SENSORS)
        entities = []
        if todo_sensors and todo_sensors.get(CONF_ENABLED):
            sensor_services = SensorServices(hass)
            await sensor_services.async_scan_for_task_lists(None)

            yaml_filename = build_yaml_filename(self._config, YAML_TASK_LISTS)
            yaml_filepath = build_config_file_path(hass, yaml_filename)
            task_dict = load_yaml_file(
                yaml_filepath, CONF_TASK_LIST_ID, TASK_LIST_SCHEMA
            )
            task_lists = list(task_dict.values())
            tasks = self._account.tasks()
            for task in task_lists:
                name = task.get(CONF_NAME)
                track = task.get(CONF_TRACK)
                task_list_id = task.get(CONF_TASK_LIST_ID)
                entity_id = _build_entity_id(hass, name, self._config)
                if not track:
                    continue
                try:
                    todo = (
                        await hass.async_add_executor_job(  # pylint: disable=no-member
                            ft.partial(
                                tasks.get_folder,
                                folder_id=task_list_id,
                            )
                        )
                    )
                    todo_sensor = O365TodoSensor(self, todo, name, entity_id)
                    entities.append(todo_sensor)
                except HTTPError:
                    _LOGGER.warning(
                        "Task list not found for: %s - Please remove from O365_tasks_%s.yaml",
                        name,
                        self._account_name,
                    )

        return entities

    async def _async_update_data(self):
        _LOGGER.debug("Doing sensor update for: %s", self._account_name)
        for entity in self._entities:
            if entity.entity_type == SENSOR_MAIL:
                await self._async_email_update(entity)
            elif entity.entity_type == SENSOR_TEAMS_STATUS:
                await self._async_teams_status_update(entity)
            elif entity.entity_type == SENSOR_TEAMS_CHAT:
                await self._async_teams_chat_update(entity)
            elif entity.entity_type == SENSOR_TODO:
                await self._async_todos_update(entity)

        return self._data

    async def _async_email_update(self, entity):
        """Update code."""
        data = await self.hass.async_add_executor_job(  # pylint: disable=no-member
            ft.partial(
                entity.mail_folder.get_messages,
                limit=entity.max_items,
                query=entity.query,
                download_attachments=entity.download_attachments,
            )
        )
        attrs = [get_email_attributes(x, entity.download_attachments) for x in data]
        attrs.sort(key=itemgetter("received"), reverse=True)
        self._data[entity.entity_id] = {
            ATTR_STATE: len(attrs),
            ATTR_ATTRIBUTES: {"data": attrs},
        }

    async def _async_teams_status_update(self, entity):
        """Update state."""
        if data := await self.hass.async_add_executor_job(entity.teams.get_my_presence):
            self._data[entity.entity_id] = {ATTR_STATE: data.activity}

    async def _async_teams_chat_update(self, entity):
        """Update state."""
        state = None
        chats = await self.hass.async_add_executor_job(entity.teams.get_my_chats)
        for chat in chats:
            messages = await self.hass.async_add_executor_job(
                ft.partial(chat.get_messages, limit=10)
            )
            for message in messages:
                if not state and message.content != "<systemEventMessage/>":
                    state = message.created_date
                    self._data[entity.entity_id] = {
                        ATTR_FROM_DISPLAY_NAME: message.from_display_name,
                        ATTR_CONTENT: message.content,
                        ATTR_CHAT_ID: message.chat_id,
                        ATTR_IMPORTANCE: message.importance,
                        ATTR_SUBJECT: message.subject,
                        ATTR_SUMMARY: message.summary,
                    }

                    break
            if state:
                break
        self._data[entity.entity_id][ATTR_STATE] = state

    async def _async_todos_update(self, entity):
        """Update state."""
        if entity.entity_id in self._data:
            error = self._data[entity.entity_id][ATTR_ERROR]
        else:
            self._data[entity.entity_id] = {ATTR_TASKS: {}, ATTR_STATE: 0}
            error = False
        try:
            data = await self.hass.async_add_executor_job(  # pylint: disable=no-member
                ft.partial(entity.todo.get_tasks, batch=100, query=entity.query)
            )
            if error:
                _LOGGER.info("Task list reconnected for: %s", entity.name)
                error = False
            tasks = list(data)
            self._data[entity.entity_id][ATTR_TASKS] = tasks
            self._data[entity.entity_id][ATTR_STATE] = len(tasks)
        except HTTPError:
            if not error:
                _LOGGER.error(
                    "Task list not found for: %s - Has it been deleted?",
                    entity.name,
                )
                error = True
        self._data[entity.entity_id][ATTR_ERROR] = error


def _build_entity_id(hass, name, conf):
    return async_generate_entity_id(
        SENSOR_ENTITY_ID_FORMAT,
        f"{name}_{conf[CONF_ACCOUNT_NAME]}",
        hass=hass,
    )


async def _async_setup_register_services(hass, conf):
    todo_sensors = conf.get(CONF_TODO_SENSORS)
    if not todo_sensors or not todo_sensors.get(CONF_ENABLED):
        return

    platform = entity_platform.async_get_current_platform()
    if conf.get(CONF_ENABLE_UPDATE):
        platform.async_register_entity_service(
            "new_task",
            NEW_TASK_SCHEMA,
            "new_task",
        )

    sensor_services = SensorServices(hass)
    hass.services.async_register(
        DOMAIN, "scan_for_task_lists", sensor_services.async_scan_for_task_lists
    )


def _get_mail_folder(account, sensor_conf, sensor_type):
    """Get the configured folder."""
    mailbox = account.mailbox()
    _LOGGER.debug("Get mail folder: %s", sensor_conf.get(CONF_NAME))
    if mail_folder_conf := sensor_conf.get(CONF_MAIL_FOLDER):
        return _get_configured_mail_folder(mail_folder_conf, mailbox, sensor_type)

    return mailbox.inbox_folder()


def _get_configured_mail_folder(mail_folder_conf, mailbox, sensor_type):
    mail_folder = None
    for i, folder in enumerate(mail_folder_conf.split("/")):
        if i == 0:
            mail_folder = mailbox.get_folder(folder_name=folder)
        else:
            mail_folder = mail_folder.get_folder(folder_name=folder)

        if not mail_folder:
            _LOGGER.error(
                "Folder - %s - not found from %s config entry - %s - entity not created",
                folder,
                sensor_type,
                mail_folder_conf,
            )
            return None

    return mail_folder


class O365Sensor(CoordinatorEntity):
    """O365 generic Sensor class."""

    def __init__(self, coordinator, name, entity_id, entity_type):
        """Initialise the O365 Sensor."""
        super().__init__(coordinator)
        self._name = name
        self._entity_id = entity_id
        self.entity_type = entity_type

    @property
    def name(self):
        """Name property."""
        return self._name

    @property
    def entity_id(self):
        """Entity_Id property."""
        return self._entity_id

    @property
    def state(self):
        """Sensor state."""
        return self.coordinator.data[self.entity_id][ATTR_STATE]


class O365MailSensor(O365Sensor):
    """O365 generic Mail Sensor class."""

    def __init__(self, coordinator, conf, mail_folder, name, entity_id):
        """Initialise the O365 Sensor."""
        super().__init__(coordinator, name, entity_id, SENSOR_MAIL)
        self.mail_folder = mail_folder
        self.download_attachments = conf.get(CONF_DOWNLOAD_ATTACHMENTS, True)
        self.max_items = conf.get(CONF_MAX_ITEMS, 5)
        self.query = None

    @property
    def icon(self):
        """Entity icon."""
        return "mdi:microsoft-outlook"

    @property
    def extra_state_attributes(self):
        """Device state attributes."""
        return self.coordinator.data[self.entity_id][ATTR_ATTRIBUTES]


class O365QuerySensor(O365MailSensor, Entity):
    """O365 Query sensor processing."""

    def __init__(self, coordinator, conf, mail_folder, name, entity_id):
        """Initialise the O365 Query."""
        super().__init__(coordinator, conf, mail_folder, name, entity_id)

        self.query = self.mail_folder.new_query()
        self.query.order_by("receivedDateTime", ascending=False)

        self._build_query(conf)

    def _build_query(self, conf):
        body_contains = conf.get(CONF_BODY_CONTAINS)
        subject_contains = conf.get(CONF_SUBJECT_CONTAINS)
        subject_is = conf.get(CONF_SUBJECT_IS)
        has_attachment = conf.get(CONF_HAS_ATTACHMENT)
        importance = conf.get(CONF_IMPORTANCE)
        email_from = conf.get(CONF_MAIL_FROM)
        is_unread = conf.get(CONF_IS_UNREAD)
        if (
            body_contains is not None
            or subject_contains is not None
            or subject_is is not None
            or has_attachment is not None
            or importance is not None
            or email_from is not None
            or is_unread is not None
        ):
            self._add_to_query("ge", "receivedDateTime", datetime.datetime(1900, 5, 1))
        self._add_to_query("contains", "body", body_contains)
        self._add_to_query("contains", "subject", subject_contains)
        self._add_to_query("equals", "subject", subject_is)
        self._add_to_query("equals", "hasAttachments", has_attachment)
        self._add_to_query("equals", "from", email_from)
        self._add_to_query("equals", "IsRead", not is_unread, is_unread)
        self._add_to_query("equals", "importance", importance)

    def _add_to_query(self, qtype, attribute_name, attribute_value, check_value=True):
        if attribute_value is None or check_value is None:
            return

        if qtype == "ge":
            self.query.chain("and").on_attribute(attribute_name).greater_equal(
                attribute_value
            )
        if qtype == "contains":
            self.query.chain("and").on_attribute(attribute_name).contains(
                attribute_value
            )
        if qtype == "equals":
            self.query.chain("and").on_attribute(attribute_name).equals(attribute_value)


class O365EmailSensor(O365MailSensor, Entity):
    """O365 Email sensor processing."""

    def __init__(self, coordinator, conf, mail_folder, name, entity_id):
        """Initialise the O365 Email sensor."""
        super().__init__(coordinator, conf, mail_folder, name, entity_id)

        is_unread = conf.get(CONF_IS_UNREAD)

        self.query = None
        if is_unread is not None:
            self.query = self.mail_folder.new_query()
            self.query.chain("and").on_attribute("IsRead").equals(not is_unread)


class O365TeamsSensor(O365Sensor):
    """O365 Teams sensor processing."""

    def __init__(self, cordinator, account, name, entity_id, entity_type):
        """Initialise the Teams Sensor."""
        super().__init__(cordinator, name, entity_id, entity_type)
        self.teams = account.teams()

    @property
    def icon(self):
        """Entity icon."""
        return "mdi:microsoft-teams"


class O365TeamsStatusSensor(O365TeamsSensor, Entity):
    """O365 Teams sensor processing."""

    def __init__(self, coordinator, account, name, entity_id):
        """Initialise the Teams Sensor."""
        super().__init__(coordinator, account, name, entity_id, SENSOR_TEAMS_STATUS)


class O365TeamsChatSensor(O365TeamsSensor, Entity):
    """O365 Teams Chat sensor processing."""

    def __init__(self, coordinator, account, name, entity_id):
        """Initialise the Teams Chat Sensor."""
        super().__init__(coordinator, account, name, entity_id, SENSOR_TEAMS_CHAT)

    @property
    def extra_state_attributes(self):
        """Return entity specific state attributes."""
        attributes = {
            ATTR_FROM_DISPLAY_NAME: self.coordinator.data[self.entity_id][
                ATTR_FROM_DISPLAY_NAME
            ],
            ATTR_CONTENT: self.coordinator.data[self.entity_id][ATTR_CONTENT],
            ATTR_CHAT_ID: self.coordinator.data[self.entity_id][ATTR_CHAT_ID],
            ATTR_IMPORTANCE: self.coordinator.data[self.entity_id][ATTR_IMPORTANCE],
        }
        if self.coordinator.data[self.entity_id][ATTR_SUBJECT]:
            attributes[ATTR_SUBJECT] = self.coordinator.data[self.entity_id][
                ATTR_SUBJECT
            ]
        if self.coordinator.data[self.entity_id][ATTR_SUMMARY]:
            attributes[ATTR_SUMMARY] = self.coordinator.data[self.entity_id][
                ATTR_SUMMARY
            ]
        return attributes


class O365TodoSensor(O365Sensor, Entity):
    """O365 Teams sensor processing."""

    def __init__(self, coordinator, todo, name, entity_id):
        """Initialise the Teams Sensor."""
        super().__init__(coordinator, name, entity_id, SENSOR_TODO)
        self.todo = todo
        self.query = self.todo.new_query("status").unequal("completed")

    @property
    def icon(self):
        """Entity icon."""
        return "mdi:clipboard-check-outline"

    @property
    def extra_state_attributes(self):
        """Extra state attributes."""
        all_tasks = []
        overdue_tasks = []
        for item in self.coordinator.data[self.entity_id][ATTR_TASKS]:
            task = {ATTR_SUBJECT: item.subject}
            if item.due:
                task[ATTR_DUE] = item.due
                if item.due < dt.utcnow():
                    overdue_tasks.append(
                        {ATTR_SUBJECT: item.subject, ATTR_DUE: item.due}
                    )

            all_tasks.append(task)

        extra_attributes = {ATTR_ALL_TASKS: all_tasks}
        if overdue_tasks:
            extra_attributes[ATTR_OVERDUE_TASKS] = overdue_tasks
        return extra_attributes

    def new_task(self, subject, description=None, due=None, reminder=None):
        """Create a new task for this task list."""
        # sourcery skip: raise-from-previous-error
        new_task = self.todo.new_task(subject=subject)
        if description:
            new_task.body = description
        if due:
            try:
                if len(due) > 10:
                    new_task.due = dt.parse_datetime(due).date()
                else:
                    new_task.due = dt.parse_date(due)
            except ValueError:
                error = f"Due date {due} is not in valid format YYYY-MM-DD"
                raise vol.Invalid(error)  # pylint: disable=raise-missing-from

        if reminder:
            new_task.reminder = reminder

        new_task.save()
        return True


class SensorServices:
    """Sensor Services."""

    def __init__(self, hass):
        """Initialise the sensor services."""
        self._hass = hass

    async def async_scan_for_task_lists(self, call):  # pylint: disable=unused-argument
        """Scan for new task lists."""
        for config in self._hass.data[DOMAIN]:
            config = self._hass.data[DOMAIN][config]
            todo_sensor = config.get(CONF_TODO_SENSORS)
            if todo_sensor and CONF_ACCOUNT in config and todo_sensor.get(CONF_ENABLED):
                todos = config[CONF_ACCOUNT].tasks()

                todolists = await self._hass.async_add_executor_job(todos.list_folders)
                track = todo_sensor.get(CONF_TRACK_NEW)
                for todo in todolists:
                    update_task_list_file(
                        build_yaml_filename(config, YAML_TASK_LISTS),
                        todo,
                        self._hass,
                        track,
                    )
