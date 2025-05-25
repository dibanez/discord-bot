import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os

# Add the parent directory (project root) to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import the function to be tested and relevant constants/exceptions
from bot import _verify_member_key, is_bot_admin
from bot import (
    MSG_VERIFY_SUCCESS,
    MSG_VERIFY_ROLE_NOT_FOUND,
    MSG_VERIFY_ERROR_CRITICAL_SHEET,
    MSG_VERIFY_ERROR_SHEET_API,
    MSG_VERIFY_ERROR_PERMISSION,
    MSG_VERIFY_ERROR_DISCORD_API,
    MSG_VERIFY_ERROR_GENERAL,
    GOOGLE_SHEET_NAME,
    GOOGLE_SHEET_TAB,  # For log messages
)
from gspread.exceptions import (
    SpreadsheetNotFound,
    WorksheetNotFound,
    APIError as GSpreadAPIError,
)

# Assuming discord.errors.Forbidden etc. are aliased or accessible in bot.py
# If not, they need to be imported directly:
# from discord.errors import Forbidden as DiscordForbiddenError, HTTPException as DiscordHTTPException
# For this exercise, we'll assume they are accessible via bot.DiscordForbiddenError etc. if used in bot.py
# or we mock where they are raised from (e.g. member.edit.side_effect = DiscordForbiddenError)
# The current bot.py imports them as:
# from discord.errors import Forbidden as DiscordForbiddenError, HTTPException as DiscordHTTPException
# So we should import them similarly if we need to type check.
from discord.errors import (
    Forbidden as DiscordForbiddenError,
    HTTPException as DiscordHTTPException,
)


class TestBotSetup(
    unittest.TestCase
):  # This can remain TestCase if its tests are synchronous

    def test_example(self):
        """A simple example test to ensure unittest is working."""
        self.assertEqual(1 + 1, 2)

    def test_true_is_true(self):
        """Another simple placeholder test."""
        self.assertTrue(True)


class TestIsBotAdmin(unittest.IsolatedAsyncioTestCase):

    async def test_user_is_admin_in_one_guild(self):
        ctx = MagicMock()
        ctx.author.id = 12345

        mock_guild = MagicMock()
        mock_member_admin = MagicMock()
        mock_member_admin.guild_permissions.administrator = True
        mock_guild.get_member.return_value = mock_member_admin

        ctx.bot.guilds = [mock_guild]

        result = await is_bot_admin(ctx)
        self.assertTrue(result)
        mock_guild.get_member.assert_called_once_with(12345)

    async def test_user_is_admin_in_another_guild_of_many(self):
        ctx = MagicMock()
        ctx.author.id = 67890

        mock_guild_no_admin = MagicMock()
        mock_member_no_admin = MagicMock()
        mock_member_no_admin.guild_permissions.administrator = False
        mock_guild_no_admin.get_member.return_value = mock_member_no_admin

        mock_guild_admin = MagicMock()
        mock_member_admin = MagicMock()
        mock_member_admin.guild_permissions.administrator = True
        mock_guild_admin.get_member.return_value = mock_member_admin

        ctx.bot.guilds = [mock_guild_no_admin, mock_guild_admin]

        result = await is_bot_admin(ctx)
        self.assertTrue(result)
        mock_guild_no_admin.get_member.assert_called_once_with(67890)
        mock_guild_admin.get_member.assert_called_once_with(67890)

    async def test_user_is_not_admin_in_any_guilds(self):
        ctx = MagicMock()
        ctx.author.id = 12345

        mock_guild1 = MagicMock()
        mock_member_not_admin1 = MagicMock()
        mock_member_not_admin1.guild_permissions.administrator = False
        mock_guild1.get_member.return_value = mock_member_not_admin1

        mock_guild2 = MagicMock()
        mock_member_not_admin2 = MagicMock()
        mock_member_not_admin2.guild_permissions.administrator = False
        mock_guild2.get_member.return_value = mock_member_not_admin2

        ctx.bot.guilds = [mock_guild1, mock_guild2]

        result = await is_bot_admin(ctx)
        self.assertFalse(result)
        mock_guild1.get_member.assert_called_once_with(12345)
        mock_guild2.get_member.assert_called_once_with(12345)

    async def test_user_not_in_any_bot_guilds(self):
        ctx = MagicMock()
        ctx.author.id = 54321

        mock_guild1 = MagicMock()
        mock_guild1.get_member.return_value = None  # User not in this guild

        mock_guild2 = MagicMock()
        mock_guild2.get_member.return_value = None  # User not in this guild

        ctx.bot.guilds = [mock_guild1, mock_guild2]

        result = await is_bot_admin(ctx)
        self.assertFalse(result)
        mock_guild1.get_member.assert_called_once_with(54321)
        mock_guild2.get_member.assert_called_once_with(54321)

    async def test_bot_in_no_guilds(self):
        ctx = MagicMock()
        ctx.author.id = 99999

        ctx.bot.guilds = []  # Bot is in no guilds

        result = await is_bot_admin(ctx)
        self.assertFalse(result)

    async def test_member_object_exists_but_no_admin_permissions_attribute(self):
        ctx = MagicMock()
        ctx.author.id = 11111

        mock_guild = MagicMock()
        mock_member_malformed = MagicMock()
        # Simulate guild_permissions existing, but 'administrator' missing or not True
        # If guild_permissions itself is missing, MagicMock default behavior is to create it.
        # If administrator is missing, it will evaluate to a new MagicMock, which is not True.
        del mock_member_malformed.guild_permissions.administrator
        # Or set it to something that's not True, e.g.
        # mock_member_malformed.guild_permissions.administrator = MagicMock(return_value=False)

        mock_guild.get_member.return_value = mock_member_malformed

        ctx.bot.guilds = [mock_guild]

        result = await is_bot_admin(ctx)
        self.assertFalse(
            result
        )  # Should not error and return False as admin status is not True
        mock_guild.get_member.assert_called_once_with(11111)

    async def test_member_object_is_none_then_admin_in_next_guild(self):
        ctx = MagicMock()
        ctx.author.id = 22222

        mock_guild_none = MagicMock()
        mock_guild_none.get_member.return_value = None  # User not in this guild

        mock_guild_admin = MagicMock()
        mock_member_admin = MagicMock()
        mock_member_admin.guild_permissions.administrator = True
        mock_guild_admin.get_member.return_value = mock_member_admin

        ctx.bot.guilds = [mock_guild_none, mock_guild_admin]

        result = await is_bot_admin(ctx)
        self.assertTrue(result)
        mock_guild_none.get_member.assert_called_once_with(22222)
        mock_guild_admin.get_member.assert_called_once_with(22222)


class TestVerifyMemberKey(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_member = MagicMock()
        self.mock_member.name = "TestUser"
        self.mock_member.id = 123456
        self.mock_member.mention = "<@123456>"
        self.mock_member.guild = MagicMock()
        self.mock_member.guild.roles = []  # Initialize for discord.utils.get
        self.mock_member.edit = AsyncMock()
        self.mock_member.add_roles = AsyncMock()
        self.mock_member.send = AsyncMock()

        self.mock_sheet = MagicMock()
        self.mock_log_channel = MagicMock()
        self.mock_log_channel.send = AsyncMock()

        self.sample_row_data = {
            "Clave": "VALIDKEY",
            "Nombre Discord": "VerifiedUser",
            "Rol Asignado": "VerifiedRole",
        }
        self.mock_sheet.get_all_records.return_value = [self.sample_row_data]

        self.mock_role = MagicMock(
            name="VerifiedRole_Mock"
        )  # Give mock_role a name for easier debugging
        self.mock_role.name = "VerifiedRole"

    @patch("bot.discord.utils.get")
    async def test_valid_key_role_found_all_success(self, mock_discord_utils_get):
        mock_discord_utils_get.return_value = self.mock_role

        result = await _verify_member_key(
            self.mock_member, "VALIDKEY", self.mock_sheet, self.mock_log_channel
        )
        self.assertTrue(result)
        self.mock_member.edit.assert_called_once_with(nick="VerifiedUser")
        self.mock_member.add_roles.assert_called_once_with(self.mock_role)
        self.mock_member.send.assert_called_once_with(
            MSG_VERIFY_SUCCESS.format(rol_nombre="VerifiedRole")
        )
        self.mock_log_channel.send.assert_called_once_with(
            f"✅ **{self.mock_member.name} ({self.mock_member.id})** verificado como `VerifiedUser` y asignado el rol `VerifiedRole`."
        )
        mock_discord_utils_get.assert_called_once_with(
            self.mock_member.guild.roles, name="VerifiedRole"
        )

    @patch("bot.discord.utils.get")
    async def test_valid_key_role_not_found(self, mock_discord_utils_get):
        mock_discord_utils_get.return_value = None  # Role not found

        result = await _verify_member_key(
            self.mock_member, "VALIDKEY", self.mock_sheet, self.mock_log_channel
        )
        self.assertTrue(result)  # Still true as key was valid
        self.mock_member.edit.assert_called_once_with(nick="VerifiedUser")
        self.mock_member.add_roles.assert_not_called()
        self.mock_member.send.assert_called_once_with(
            MSG_VERIFY_ROLE_NOT_FOUND.format(rol_nombre="VerifiedRole")
        )
        self.mock_log_channel.send.assert_called_once_with(
            f"⚠️ **{self.mock_member.name} ({self.mock_member.id})** tenía clave válida, pero rol `VerifiedRole` no encontrado."
        )

    async def test_invalid_key(self):
        result = await _verify_member_key(
            self.mock_member, "INVALIDKEY", self.mock_sheet, self.mock_log_channel
        )
        self.assertFalse(result)
        self.mock_member.edit.assert_not_called()
        self.mock_member.add_roles.assert_not_called()
        # _verify_member_key no longer sends MSG_VERIFY_KEY_INCORRECT, this is handled by on_member_join retry logic
        self.mock_member.send.assert_not_called()
        self.mock_log_channel.send.assert_called_once_with(
            f"ℹ️ Intento de clave fallido para {self.mock_member.name} ({self.mock_member.id}) con clave: 'INVALIDKEY'"
        )

    async def test_sheet_spreadsheet_not_found(self):
        self.mock_sheet.get_all_records.side_effect = SpreadsheetNotFound
        result = await _verify_member_key(
            self.mock_member, "VALIDKEY", self.mock_sheet, self.mock_log_channel
        )
        self.assertFalse(result)
        self.mock_member.send.assert_called_once_with(MSG_VERIFY_ERROR_CRITICAL_SHEET)
        self.mock_log_channel.send.assert_called_once_with(
            f"❗ **ERROR CRÍTICO:** Hoja de cálculo '{GOOGLE_SHEET_NAME}' no encontrada. User: {self.mock_member.name} ({self.mock_member.id})"
        )

    async def test_sheet_worksheet_not_found(self):
        self.mock_sheet.get_all_records.side_effect = WorksheetNotFound
        # The current code in _verify_member_key sends MSG_VERIFY_ERROR_CRITICAL_SHEET
        # and logs to current_log_channel.send with specific message for WorksheetNotFound
        # However, it sends MSG_VERIFY_ERROR_CRITICAL_SHEET to the log channel as well, which seems like a copy-paste error.
        # Assuming it should send the specific error message to the user, or the critical sheet error.
        # The current implementation sends MSG_VERIFY_ERROR_CRITICAL_SHEET to member, and specific log to log_channel
        # then sends MSG_VERIFY_ERROR_CRITICAL_SHEET to log_channel. This last one is likely wrong.
        # For now, testing current behavior.

        result = await _verify_member_key(
            self.mock_member, "VALIDKEY", self.mock_sheet, self.mock_log_channel
        )
        self.assertFalse(result)
        self.mock_member.send.assert_called_once_with(MSG_VERIFY_ERROR_CRITICAL_SHEET)
        # First log call
        self.mock_log_channel.send.assert_any_call(
            f"❗ **ERROR CRÍTICO:** Pestaña '{GOOGLE_SHEET_TAB}' no encontrada en '{GOOGLE_SHEET_NAME}'. User: {self.mock_member.name} ({self.mock_member.id})"
        )
        # Second log call (which is likely unintended in bot.py)
        self.mock_log_channel.send.assert_any_call(MSG_VERIFY_ERROR_CRITICAL_SHEET)

    async def test_sheet_gspread_api_error(self):
        self.mock_sheet.get_all_records.side_effect = GSpreadAPIError("API Error")
        result = await _verify_member_key(
            self.mock_member, "VALIDKEY", self.mock_sheet, self.mock_log_channel
        )
        self.assertFalse(result)
        self.mock_member.send.assert_called_once_with(MSG_VERIFY_ERROR_SHEET_API)
        self.mock_log_channel.send.assert_called_once_with(
            f"❗ **ERROR API GOOGLE:** API Error al leer la hoja. User: {self.mock_member.name} ({self.mock_member.id})"
        )

    @patch("bot.discord.utils.get")
    async def test_member_edit_forbidden(self, mock_discord_utils_get):
        mock_discord_utils_get.return_value = self.mock_role
        self.mock_member.edit.side_effect = DiscordForbiddenError(
            MagicMock(), "Cannot edit nick"
        )

        result = await _verify_member_key(
            self.mock_member, "VALIDKEY", self.mock_sheet, self.mock_log_channel
        )
        self.assertTrue(result)  # Partial success
        self.mock_log_channel.send.assert_any_call(
            f"⚠️ **Permiso denegado:** No se pudo cambiar el apodo de {self.mock_member.mention} ({self.mock_member.id}) a 'VerifiedUser'."
        )
        self.mock_member.add_roles.assert_called_once_with(
            self.mock_role
        )  # Should still try to add role

    @patch("bot.discord.utils.get")
    async def test_member_add_roles_forbidden(self, mock_discord_utils_get):
        mock_discord_utils_get.return_value = self.mock_role
        self.mock_member.add_roles.side_effect = DiscordForbiddenError(
            MagicMock(), "Cannot add role"
        )

        result = await _verify_member_key(
            self.mock_member, "VALIDKEY", self.mock_sheet, self.mock_log_channel
        )
        self.assertTrue(result)
        self.mock_log_channel.send.assert_any_call(
            f"⚠️ **Permiso denegado:** No se pudo asignar el rol 'VerifiedRole' a {self.mock_member.mention} ({self.mock_member.id})."
        )
        self.mock_member.send.assert_any_call(
            MSG_VERIFY_ERROR_PERMISSION + " (No se pudo asignar el rol 'VerifiedRole')"
        )

    @patch("bot.discord.utils.get")
    async def test_member_send_fails_after_success(self, mock_discord_utils_get):
        mock_discord_utils_get.return_value = self.mock_role
        # First send (success message) fails
        self.mock_member.send.side_effect = DiscordForbiddenError(
            MagicMock(), "Cannot send DM"
        )

        result = await _verify_member_key(
            self.mock_member, "VALIDKEY", self.mock_sheet, self.mock_log_channel
        )
        # The function might return True because core logic (edit, add_roles) was attempted/successful
        # or False if it considers inability to notify user a failure.
        # Current _verify_member_key has a general try-except for member.send for these cases.
        # If MSG_VERIFY_SUCCESS fails, it's caught by the general (DiscordForbiddenError, DiscordHTTPException) block
        self.assertFalse(
            result
        )  # Because the DM send error is caught and returns False

        self.mock_member.edit.assert_called_once_with(nick="VerifiedUser")
        self.mock_member.add_roles.assert_called_once_with(self.mock_role)
        self.mock_log_channel.send.assert_any_call(
            f"❗ Error enviando DM a {self.mock_member.name} ({self.mock_member.id}) durante _verify_member_key (e.g. user blocked DMs): {self.mock_member.send.side_effect}"
        )

    @patch("bot.discord.utils.get")
    async def test_log_channel_send_fails(self, mock_discord_utils_get):
        mock_discord_utils_get.return_value = self.mock_role
        self.mock_log_channel.send.side_effect = DiscordHTTPException(
            MagicMock(), "Log channel send failed"
        )

        # Even if logging fails, user-facing actions should complete.
        result = await _verify_member_key(
            self.mock_member, "VALIDKEY", self.mock_sheet, self.mock_log_channel
        )
        self.assertTrue(result)
        self.mock_member.edit.assert_called_once_with(nick="VerifiedUser")
        self.mock_member.add_roles.assert_called_once_with(self.mock_role)
        self.mock_member.send.assert_called_once_with(
            MSG_VERIFY_SUCCESS.format(rol_nombre="VerifiedRole")
        )
        # Log channel send was called, but it raised an exception (which is fine for this test, not caught by _verify_member_key)
        self.assertTrue(self.mock_log_channel.send.called)

    async def test_generic_exception_during_processing(self):
        self.mock_sheet.get_all_records.side_effect = Exception("Some generic error")
        result = await _verify_member_key(
            self.mock_member, "VALIDKEY", self.mock_sheet, self.mock_log_channel
        )
        self.assertFalse(result)
        self.mock_member.send.assert_called_once_with(MSG_VERIFY_ERROR_GENERAL)
        self.mock_log_channel.send.assert_called_once_with(
            f"❗ Error interno no esperado verificando a **{self.mock_member.name} ({self.mock_member.id})**: `Some generic error`"
        )


if __name__ == "__main__":
    unittest.main()
