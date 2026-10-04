from plugins.start import register_start
from plugins.profile import register_profile
from plugins.deposit import register_deposit
from plugins.buy import register_buy
from plugins.admin import register_admin
from plugins.admin_actions import register_admin_actions
from plugins.callbacks import register_callbacks
from plugins.smm import register_smm
from plugins.source_codes import register_source_codes
from plugins.panels import register_panels

def register_all_handlers(bot):
    register_start(bot)
    register_profile(bot)
    register_deposit(bot)
    register_buy(bot)
    register_admin(bot)
    register_admin_actions(bot)
    register_callbacks(bot)
    register_smm(bot)
    register_source_codes(bot)
    register_panels(bot)
