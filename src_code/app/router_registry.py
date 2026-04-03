# app/router_registry.py

from app.routes.SigninGraphQLRoute import router as signin_graphql_route
from app.routes.SignupGraphQLRoute import router as signup_graphql_route
from app.routes.DeviceMasterRoutes import router as device_master_router
from app.routes.DeviceSettingRoutes import router as device_setting_router
from app.routes.DeviceMasterGraphQLRoute import router as device_master_graphql_router
from app.routes.AnalyticsDataGraphQLRoute import router as analytics_graphql_router
from app.routes.CommandRoutes import router as command_router
from app.routes.CommandSentRoutes import router as command_sent_router
from app.routes.CommandResponseRoutes import router as command_response_router
from app.routes.GeofenceRoutes import router as genofence_router
from app.routes.SigninRoutes import router as signin
from app.routes.TataSubscriptionRoutes import router as tata_api_router
from app.routes.SosRoutes import router as sos_router

router_registry = []

router_registry += [
    {
        "router": signin_graphql_route,
        "prefix": "/auth",
        "tags": ["Signin GraphQL"],
        "include_in_schema": True,
    },
    {
        "router": signup_graphql_route,
        "prefix": "/auth",
        "tags": ["Signup GraphQL"],
        "include_in_schema": True,
    },
    {
        "router": device_master_router,
        "prefix": "/device",
        "tags": ["Device Master "],
        "include_in_schema": True,
    },
    {
        "router": device_setting_router,
        "prefix": "/setting",
        "tags": ["Device Setting "],
        "include_in_schema": True,
    },
    {
        "router": device_master_graphql_router,
        "prefix": "/device",
        "tags": ["Device Master GraphQl"],
        "include_in_schema": True,
    },
    {
        "router": analytics_graphql_router,
        "prefix": "/analytics",
        "tags": ["Telemetry Analysis"],
        "include_in_schema": True,
    },
    {
        "router": command_router,
        "prefix": "",
        "tags": ["Query Command"],
        "include_in_schema": True,
    },
    {
        "router": command_sent_router,
        "prefix": "",
        "tags": ["Query Command"],
        "include_in_schema": True,
    },
    {
        "router": command_response_router,
        "prefix": "",
        "tags": ["Query Command"],
        "include_in_schema": True,
    },
    {
        "router": genofence_router,
        "prefix": "",
        "tags": ["Genofence Data"],
        "include_in_schema": True,
    },
    {
        "router": signin,
        "prefix": "/auth",
        "tags": ["Signin"],
        "include_in_schema": True,
    },
    {
        "router": tata_api_router,
        "prefix": "/tata",
        "tags": ["Tata API Services"],
        "include_in_schema": True,
    },
    {
        "router": sos_router,
        "prefix": "",
        "tags": ["SOS Notification"],
        "include_in_schema": False,
    },
]
