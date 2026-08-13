from api.endpoints.action_items import router as action_items_router
from api.endpoints.alert import router as alert_router
from api.endpoints.auth import router as auth_router
from api.endpoints.black_domain import router as black_domain_router
from api.endpoints.categorized_event import router as categorized_event_router
from api.endpoints.category import router as category_router
from api.endpoints.channel import router as channel_router
from api.endpoints.competitor import router as competitor_router
from api.endpoints.department import router as department_router
from api.endpoints.event_type import router as event_type_router
from api.endpoints.filter_options import router as filter_options_router
from api.endpoints.normalized_item import router as normalized_item_router
from api.endpoints.raw_item import router as raw_item_router
from api.endpoints.region import router as region_router
from api.endpoints.routing_rule import router as routing_rule_router
from api.endpoints.search_task import router as search_task_router
from api.endpoints.showcase import router as showcase_router
from api.endpoints.source import router as source_router
from api.endpoints.source_candidate import router as source_candidate_router
from api.endpoints.stop_word import router as stop_word_router
from api.endpoints.topic_limit import router as topic_limit_router
from api.endpoints.trigger import router as trigger_router
from api.endpoints.users import router as users_router

__all__ = [
    'action_items_router',
    'alert_router',
    'auth_router',
    'black_domain_router',
    'categorized_event_router',
    'category_router',
    'channel_router',
    'competitor_router',
    'department_router',
    'event_type_router',
    'filter_options_router',
    'normalized_item_router',
    'raw_item_router',
    'region_router',
    'routing_rule_router',
    'search_task_router',
    'showcase_router',
    'source_candidate_router',
    'source_router',
    'stop_word_router',
    'topic_limit_router',
    'trigger_router',
    'users_router',
]
