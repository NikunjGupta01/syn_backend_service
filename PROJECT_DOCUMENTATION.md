# Synquerra Backend Documentation

## 1. Purpose of This Document

This document is a handoff guide for taking over the Synquerra backend service.

It is written for someone who:

- is new to this codebase
- is newer to Python backend development
- knows Laravel and Node.js better than FastAPI
- does not yet know MQTT, RabbitMQ, Redis, GraphQL, or some of the surrounding infrastructure

The goal is to explain:

- what this backend does
- how the project is structured
- how requests move through the system
- what each external service is used for
- what concepts are important first
- where to start making safe changes

---

## 2. Project Summary

This project is a **FastAPI-based Python backend** for a **device/telemetry platform**.

The business domain appears to be GPS/IoT tracking devices. The backend handles:

- user signup and signin
- telemetry and analytics data retrieval
- device master records
- device command publishing
- geofence storage
- SOS event notifications
- Tata telecom/subscription API integration

It is not just a simple CRUD API. It interacts with multiple services:

- MongoDB
- Redis
- MQTT broker
- RabbitMQ
- Tata external APIs
- WebSocket clients

---

## 3. High-Level Architecture

At a high level, the system looks like this:

1. Clients call REST endpoints or GraphQL endpoints.
2. FastAPI routes forward requests into controllers or GraphQL resolvers.
3. Controllers query MongoDB using ODMantic.
4. Some requests also interact with Redis, MQTT, WebSockets, or external Tata APIs.
5. Responses are returned in a standardized response envelope.

You can think of the layers like this:

- `app/main.py` = application bootstrap
- `app/router_registry.py` = central route registration
- `app/routes/*` = HTTP/WebSocket route definitions
- `app/controllers/*` = business logic handlers
- `app/models/*` = MongoDB document models
- `app/graphql/*` = GraphQL schemas and resolvers
- `app/services/*` = background services or external integrations
- `app/libraries/*` = reusable infra helpers like logging, MQTT, RabbitMQ
- `app/helpers/*` = utility classes for JWT, validation, formatting, etc.

---

## 4. Tech Stack

Core framework and libraries used in this repo:

- **FastAPI**: web framework for REST APIs
- **Uvicorn**: ASGI server that runs the FastAPI app
- **Pydantic**: request/data validation
- **ODMantic**: object-document mapper for MongoDB
- **Motor**: async MongoDB driver
- **Strawberry GraphQL**: GraphQL schema and resolver library
- **Redis**: rate limiting
- **Paho MQTT**: MQTT publishing client
- **Pika**: RabbitMQ publishing client
- **PyJWT / python-jose**: JWT auth support
- **httpx**: async HTTP client for external APIs
- **WebSockets**: push-based SOS notifications

Main dependency file:

- `src_code/requirements.txt`

---

## 5. Project Structure

Top-level layout:

```text
backend_service/
├── .env
├── README.md
├── docker-compose.yml
├── Dockerfile_local
├── logs/
└── src_code/
    ├── requirements.txt
    ├── VERSION.txt
    └── app/
        ├── main.py
        ├── router_registry.py
        ├── config/
        ├── constants/
        ├── controllers/
        ├── graphql/
        ├── helpers/
        ├── libraries/
        ├── middleware/
        ├── models/
        ├── net/
        ├── routes/
        ├── services/
        └── websocket/
```

### Key files to learn first

- `src_code/app/main.py`
- `src_code/app/router_registry.py`
- `src_code/app/config/config.py`
- `src_code/app/models/__init__.py`
- `src_code/app/controllers/SigninController.py`
- `src_code/app/controllers/AnalyticsDataController.py`
- `src_code/app/graphql/AnalyticsDataSchema.py`
- `src_code/app/controllers/CommandController.py`

---

## 6. How the Application Starts

The main application entrypoint is:

- `src_code/app/main.py`

When the app starts:

1. FastAPI app instance is created.
2. MongoDB connection is initialized via `init_db()`.
3. Redis is initialized via `init_redis()`.
4. A background SOS watcher task is started.
5. All routers from `router_registry.py` are registered.
6. Rate-limiting middleware is attached.
7. Health endpoints and docs endpoints are exposed.

Important startup concepts:

- **lifespan** is used for app startup/shutdown work
- there is also an `@app.on_event("startup")` section
- the app creates a shared HTTP client
- the app currently starts the SOS watcher in more than one place, which is something to be aware of during refactoring

---

## 7. Configuration and Environment Variables

Config is loaded through:

- `src_code/app/config/config.py`

This file uses:

- `.env`
- `pydantic-settings`
- a version file `src_code/VERSION.txt`

### What the config contains

- app name, version, timezone, environment
- MongoDB connection values
- Redis connection
- JWT settings
- MQTT broker settings
- Tata API credentials
- logging and RabbitMQ logging settings
- encryption settings
- CORS/frontend origin values

### Important note

`config.py` updates `APP_VERSION` in `.env` by reading from `VERSION.txt`. That is a little unusual. If versioning behaves strangely, check this file first.

---

## 8. Main Data Storage: MongoDB

This project uses **MongoDB**, which is a document database.

If you come from Laravel/MySQL or Node/Postgres, think of this difference:

- SQL database: rows in tables
- MongoDB: JSON-like documents in collections

### How Mongo is used here

- connection is created in `src_code/app/models/__init__.py`
- ODMantic models define collection structure
- the app uses `find`, `find_one`, `save`, and `count`

### Main collections/models

#### `User`

File:

- `src_code/app/models/User.py`

Used for:

- signup/signin
- account metadata
- password hash and verification data

Collection:

- `sq_users`

#### `AnalyticsData`

File:

- `src_code/app/models/AnalyticsData.py`

Used for:

- telemetry packets
- alert data
- GPS-related analytics
- time-series-like device information

Collection:

- `analytics_data`

#### `DeviceMaster`

File:

- `src_code/app/models/DeviceMaster.py`

Used for:

- master records of known devices

Collection:

- `devices_master`

#### `GeofenceData`

File:

- `src_code/app/models/GeofenceData.py`

Used for:

- storing geofence shapes and metadata per device

Collection:

- `geofence_data`

#### `DeviceCommand`

File:

- `src_code/app/models/DeviceCommand.py`

Used for:

- tracking commands sent to devices

Collection:

- `device_commands`

### ODMantic in simple terms

ODMantic is similar to an ORM, but for MongoDB.

You can think of it like:

- Eloquent for Mongo documents
- Mongoose-style modeling, but Pythonic and async

Typical pattern:

```python
db = get_db()
user = await db.find_one(User, {"EMAIL": email})
await db.save(new_user)
```

---

## 9. HTTP Layer: FastAPI

FastAPI is the main web framework.

If you know Node.js:

- FastAPI is roughly like Express, but strongly typed

If you know Laravel:

- it fills the role of routing + request validation + controller handling

### Route registration

Routes are centrally assembled in:

- `src_code/app/router_registry.py`

That file imports routers from different route modules and registers them with prefixes like:

- `/auth`
- `/device`
- `/analytics`
- `/tata`

### Request flow pattern

Most REST requests follow this path:

1. route file receives request
2. route function validates input using Pydantic
3. controller executes business logic
4. database/service call happens
5. standardized JSON response is returned

Example:

- `src_code/app/routes/SigninRoutes.py`
- `src_code/app/controllers/SigninController.py`

---

## 10. Standard Response Format

Responses are shaped by:

- `src_code/app/controllers/APIResponse.py`

This class produces a common response envelope.

Typical success response contains:

- `status`
- `code`
- `request_id`
- `message`
- `timestamp`
- `data`

Typical error response contains:

- `status`
- `code`
- `request_id`
- `error_description`
- `timestamp`

There is also support for encrypting response payloads depending on settings.

---

## 11. Authentication: JWT, Signup, and Signin

### Signup

Files:

- `src_code/app/controllers/SignupController.py`
- `src_code/app/routes/SignupRoutes.py`

Flow:

1. validate request fields
2. sanitize names
3. check duplicate email/mobile in MongoDB
4. hash password using Argon2
5. save user
6. return masked user data

### Signin

Files:

- `src_code/app/controllers/SigninController.py`
- `src_code/app/routes/SigninRoutes.py`

Flow:

1. receive email/password
2. query user by email
3. verify password hash
4. generate JWT tokens
5. update last login metadata asynchronously
6. return tokens plus user profile data

### JWT

File:

- `src_code/app/helpers/JWTManager.py`

What JWT means:

- JWT = JSON Web Token
- it is a signed token used for authentication
- after login, the backend returns a token
- later requests can use that token instead of sending credentials again

This app creates:

- access token
- refresh token

In simple terms:

- access token = short-lived token used on normal requests
- refresh token = longer-lived token used to get new access tokens

---

## 12. GraphQL in This Project

GraphQL files are in:

- `src_code/app/graphql/`
- `src_code/app/routes/*GraphQLRoute.py`

Main schemas include:

- `SigninGraphQLSchema.py`
- `SignupGraphQLSchema.py`
- `DeviceMasterGraphQLSchema.py`
- `AnalyticsDataSchema.py`

### What GraphQL is

GraphQL is an alternative to REST.

With REST:

- you call many fixed endpoints like `/users`, `/devices`, `/analytics`

With GraphQL:

- the client sends a query describing exactly which fields it wants

Example idea:

```graphql
query {
  analyticsDataByImei(imei: "123456789012345") {
    imei
    latitude
    longitude
    timestamp
  }
}
```

### How GraphQL is used here

In this codebase, GraphQL is mostly a **wrapper around existing REST/controller logic**.

That means:

- the core business logic still lives mainly in controllers
- GraphQL resolvers often call route/controller functions
- you do not need to treat GraphQL as a completely separate backend architecture here

This is good news for takeover:

- learn the REST/controller flow first
- then understand the GraphQL layer as another interface to the same data

---

## 13. Redis and Rate Limiting

Redis usage lives mainly in:

- `src_code/app/middleware/redis_rate_limiter.py`

### What Redis is

Redis is an in-memory key-value store.

People commonly use it for:

- caching
- session storage
- rate limiting
- queues
- temporary counters

### What Redis is doing here

In this app, Redis is mainly used for **API rate limiting**.

The middleware:

1. reads the API key from request headers
2. checks allowed request counts per endpoint
3. stores timestamps in Redis
4. blocks requests that exceed the limit window

So Redis is not the main data database here. MongoDB is the main data store. Redis is supporting infrastructure.

### Mental model

- MongoDB = permanent application data
- Redis = fast temporary operational data

---

## 14. MQTT Explained

MQTT is one of the most important things to understand in this project.

Files:

- `src_code/app/libraries/MqttConnector.py`
- `src_code/app/controllers/CommandController.py`
- `src_code/app/constants/CommandDefinitions.py`

### What MQTT is

MQTT is a lightweight messaging protocol designed for devices, especially IoT systems.

It is very common when devices:

- are low power
- have unstable networks
- send small messages
- need pub/sub style communication

### Pub/Sub concept

MQTT uses **publish/subscribe** messaging.

Instead of:

- client directly calling another device like normal HTTP

You have:

- a **broker**
- a **publisher**
- a **subscriber**
- a **topic**

### Example

Imagine:

- backend publishes a command to topic `123456789012345/sub`
- the device is subscribed to that topic
- the MQTT broker delivers the message to the device

### Terms in plain English

#### Broker

The central server that receives and forwards MQTT messages.

In local Docker, this is:

- `eclipse-mosquitto`

#### Topic

A string used like a channel name.

Examples:

- `device123/sub`
- `imei/sub`

#### Publish

Send a message into a topic.

#### Subscribe

Listen for messages on a topic.

#### QoS

QoS = Quality of Service.

This defines how reliably delivery should happen.

Common values:

- `0` = at most once
- `1` = at least once
- `2` = exactly once

In this app, command definitions include a `qos` value.

### Why MQTT is used here

HTTP is not ideal for many always-on device messaging scenarios.

MQTT is a better fit for:

- sending device commands
- keeping overhead low
- brokered communication with IoT devices

### How this app uses MQTT

When a client calls the command send API:

1. request is validated
2. command name is checked against `COMMAND_DEFINITIONS`
3. payload is built
4. backend publishes JSON to an MQTT topic
5. command is stored in MongoDB
6. geofence data may also be saved if relevant

File:

- `src_code/app/controllers/CommandController.py`

This makes MQTT a **core runtime dependency**, not an optional one.

### Quick comparison: MQTT vs HTTP

- HTTP is request/response and heavier
- MQTT is lightweight, pub/sub, and device-friendly

If you are from Laravel/Node web apps, MQTT is the part that is most different from a normal backend stack.

---

## 15. RabbitMQ Explained

Files:

- `src_code/app/libraries/RabbitMQ.py`
- `src_code/app/helpers/RMQHelper.py`
- `src_code/app/libraries/Logger.py`

### What RabbitMQ is

RabbitMQ is a message broker, but it is used differently from MQTT.

Both MQTT and RabbitMQ move messages, but they usually solve different problems.

### Simplified difference

- **MQTT**: often used for communication with devices/IoT clients
- **RabbitMQ**: often used for backend-to-backend messaging, queues, background jobs, and log/event pipelines

### How RabbitMQ is used in this app

RabbitMQ here appears to be mainly used for **logging / ELK-style log shipping**, not for device commands.

In `Logger.py`:

- if ELK logging is enabled
- logs are pushed to RabbitMQ instead of only local file logging

In `RabbitMQ.py`:

- the app opens a RabbitMQ connection
- declares a queue
- publishes log messages into it

In `RMQHelper.py`:

- there is also a helper that sends log data to a RabbitMQ-related HTTP API

### Why that matters

For takeover purposes:

- **MQTT is business-critical**
- **RabbitMQ looks operational/logging-focused**

So if you are learning in order:

1. learn Mongo
2. learn FastAPI request flow
3. learn MQTT
4. understand Redis
5. understand RabbitMQ after that

### RabbitMQ mental model

Think of RabbitMQ like:

- a mailroom or delivery hub for internal backend messages

A producer sends a message into RabbitMQ, and another backend system or worker can process it later.

That is different from direct API calls, where both sides must be available immediately.

---

## 16. MQTT vs RabbitMQ

This is a common confusion, so here is the practical difference in this project.

### MQTT

- used to publish commands toward devices
- optimized for IoT/device messaging
- topic-based
- lightweight
- core to command delivery

### RabbitMQ

- used for log/event pipeline style messaging
- queue-oriented backend infrastructure
- not the main device-command path in this codebase
- likely more important for operations/observability than for core business logic

### Practical takeaway

If commands to devices stop working, check MQTT first.

If operational logs are missing from downstream systems, check RabbitMQ or ELK logging settings.

---

## 17. WebSockets and SOS Alerts

Files:

- `src_code/app/services/SosWatcherService.py`
- `src_code/app/routes/SosRoutes.py`
- `src_code/app/controllers/SosController.py`
- `src_code/app/websocket/ConnectionManager.py`

### What WebSocket is

WebSocket is a persistent two-way connection between client and server.

Unlike HTTP:

- HTTP opens a request, gets a response, then closes

With WebSocket:

- connection stays open
- server can push data to the client immediately

### How it is used here

This app watches MongoDB for newly inserted analytics records.

If a record contains:

- alert code `A1002`
- and `sos_disabled` is not set

then the app broadcasts an SOS payload to all connected WebSocket clients.

This means the flow is:

1. data lands in MongoDB
2. change stream watcher sees it
3. backend checks alert code
4. backend pushes SOS event to connected clients

This is a real-time notification feature.

---

## 18. Tata API Integration

Files:

- `src_code/app/routes/TataSubscriptionRoutes.py`
- `src_code/app/services/TataSubscriptionService.py`

This part of the system acts as a wrapper around Tata APIs.

Capabilities include:

- subscription lookup
- device info lookup
- plan retrieval and renewal
- SIM state changes
- SMS operations
- whitelist operations

### Mental model

This is not internal business logic in the same sense as telemetry models.

It is an **integration layer**:

- the backend receives a request
- forwards it to Tata with proper headers
- returns Tata’s response

So if those features fail, debugging should include:

- API credentials
- Tata endpoint URL
- request headers
- network connectivity
- response status from Tata

---

## 19. Logging

Logging is handled by:

- `src_code/app/libraries/Logger.py`

Key features:

- singleton logger instance
- daily log files
- retention policy
- request UUID tagging
- optional ELK/RabbitMQ forwarding

Local log files are written under the `logs/` directory.

This is useful during takeover because you can often understand app behavior by following request IDs in logs.

---

## 20. API Security and Middleware

Important middleware and helpers include:

- `src_code/app/middleware/redis_rate_limiter.py`
- `src_code/app/helpers/ValidationHelper.py`
- `src_code/app/helpers/JWTManager.py`

Security-related behavior includes:

- request rate limiting with Redis
- JWT generation and verification
- password hashing with Argon2
- optional data encryption in API responses
- some HTTP header security logic in `main.py` (currently not fully enabled)

There is also:

- `src_code/app/controllers/HMACAuth.py`

This appears to support HMAC-based request signing for certain clients, though it does not appear central to the main request paths we inspected.

---

## 21. Main Business Flows

### A. User Signin Flow

1. client calls `/auth/signin`
2. request is validated with Pydantic
3. user document is fetched from MongoDB
4. Argon2 password verification happens
5. JWT access and refresh tokens are created
6. login metadata is updated
7. standardized response is returned

### B. Analytics Query Flow

1. client calls analytics REST or GraphQL endpoint
2. backend queries `analytics_data` collection
3. records are serialized into API-friendly shape
4. analytics calculations may run for distance, uptime, health
5. response is returned

### C. Command Send Flow

1. client sends command request to `/send`
2. backend validates IMEI, command, and params
3. command definition is loaded
4. payload is published to MQTT topic
5. command record is stored in MongoDB
6. if geofence command, geofence document is also stored
7. API returns command status

### D. SOS Notification Flow

1. analytics data is inserted into MongoDB
2. change stream watcher sees new insert
3. if alert indicates SOS, app prepares event payload
4. event is broadcast to connected WebSocket clients

---

## 22. Docker / Local Infrastructure

Local infrastructure is described in:

- `docker-compose.yml`
- `Dockerfile_local`

### Services in docker-compose

- `backend`
- `mongo`
- `redis`
- `rabbitmq`
- `mqtt`

### Ports

- backend: `8000:8000` in compose
- mongo: `27017`
- redis: `6379`
- rabbitmq: `5672`
- rabbitmq management UI: `15672`
- mqtt: `1883`

### Important note

There is a mismatch to be aware of:

- `Dockerfile_local` exposes and runs on port `80`
- `docker-compose.yml` maps `8000:8000`

That may need cleanup depending on how the project is being run locally.

---

## 23. Things That May Feel Different From Laravel/Node

### `async` and `await`

Python async is used throughout this project.

You will see:

```python
async def some_handler(...):
    data = await db.find(...)
```

This is similar to:

- `async/await` in Node.js

### Pydantic models

Pydantic classes are used for request validation.

This is similar to:

- Laravel Form Requests
- Joi/Zod schemas in Node

### ODMantic instead of SQL ORM

This is document-oriented, not relational.

So think less in joins and more in document queries.

### GraphQL resolvers

GraphQL files may look unfamiliar, but many of them are just another layer that calls existing controller logic.

---

## 24. Recommended Learning Order

If you are taking over the project, learn in this order:

1. `src_code/app/main.py`
2. `src_code/app/router_registry.py`
3. `src_code/app/config/config.py`
4. `src_code/app/models/__init__.py`
5. auth flow
6. analytics flow
7. command + MQTT flow
8. Redis rate limiter
9. SOS WebSocket flow
10. RabbitMQ logging path

This order gets you productive fastest.

---

## 25. Suggested First Tasks for a New Maintainer

These are good starter tasks to understand the system safely:

1. Run the app locally and open `/docs`.
2. Trace one signin request end to end.
3. Trace one analytics GraphQL query end to end.
4. Trace one device command publish end to end.
5. Inspect one log file while making a request.
6. Confirm which external services are mandatory in your environment.

After that, good cleanup targets are:

1. document every route and expected request/response shape
2. add tests for auth and analytics
3. reduce duplicate startup logic in `main.py`
4. standardize field naming across models and serializers
5. document operational dependencies and required env vars

---

## 26. Current Risks / Rough Edges Observed

During review, a few maintainability issues stood out:

- there does not appear to be a real test suite in the repo right now
- startup logic in `main.py` has some duplication
- naming is inconsistent across snake_case, camelCase, and Pascal-style DB fields
- GraphQL and REST responsibilities are somewhat mixed
- Docker port configuration may be inconsistent

These are normal takeover notes, not blockers. Just keep them in mind when changing behavior.

---

## 27. Core vs Supporting Infrastructure

This is the shortest way to prioritize your learning.

### Core to business behavior

- FastAPI
- MongoDB
- ODMantic
- analytics data model
- device command flow
- MQTT

### Important but supporting

- Redis
- WebSockets
- JWT
- GraphQL

### Useful but likely secondary for first-week ownership

- RabbitMQ logging
- HMAC helper
- Tata integration details, unless your team actively works on that area

---

## 28. Plain-English Glossary

### FastAPI

Python web framework used to build the API.

### Uvicorn

Server that runs the FastAPI app.

### MongoDB

Document database used as the main datastore.

### ODMantic

MongoDB object mapper used like an async model layer.

### Redis

Fast in-memory store used here mainly for rate limiting.

### MQTT

Lightweight pub/sub protocol used to send messages to devices.

### RabbitMQ

Queue/message broker used here mainly for backend logging/event flow.

### GraphQL

Query language/API style that lets clients request specific fields.

### WebSocket

Persistent connection allowing the server to push real-time events to clients.

### JWT

Signed authentication token used after login.

### IMEI

A unique numeric identifier for a device.

### QoS

MQTT delivery reliability level.

### Change Stream

MongoDB feature that lets the app watch for database changes in real time.

---

## 29. Final Takeover Advice

If you are coming from Laravel and Node, you are already closer to this codebase than it may first feel.

The main new things are:

- Python syntax and async patterns
- Mongo instead of SQL
- MQTT/device messaging
- GraphQL syntax

The main app design is still familiar:

- routes
- controllers
- models
- validation
- auth
- integrations

The most important concept to learn well in this project is **how device commands move through MQTT**, because that is the least like traditional web backends and the most domain-specific part of the stack.

After that, the rest becomes much easier to reason about.
