import discord
from discord import ui, app_commands
from discord.ext import commands


MAX_COMPONENTS = 40


class CV2BuilderUI(ui.LayoutView):
    def __init__(self):
        self.components_list: list[list[ui.Item] | ui.Item] = []

        self.build_page()

    @property
    def total_components(self):
        return sum(
            1
            for _ in self.walk_children()
        )

    def build_page(self):
        self.render_components()
        self.build_control()

    def render_components(self):
        for component in self.components_list:
            if isinstance(component, list):
                container = ui.Container()
                for item in component: 
                    component.add_item(item)
                continue
                
            self.add_item(component)

    def build_control(self):
        add_select_menu = ui.Select(
            placeholder="Select a layout to add.",
            custom_id="cv2_builder_selection",
            min_values=1,
            max_values=1,
            choices=[
                discord.SelectOption(
                    label="Container",
                    value="container",
                    description="Add a container"
                ),
                discord.SelectOption(
                    label="Text",
                    value="textdisplay",
                    description="Add a text"
                ), 
                discord.SelectOption(
                    label="Line",
                    value="separator",
                    description="Add a line"
                ), 
                discord.SelectOption(
                    label="Section",
                    value="section",
                    description="Add a section"
                ), 
                discord.SelectOption(
                    label="Image",
                    value="mediagalary",
                    description="Add an image"
                ), 
                discord.SelectOption(
                    label="File",
                    value="file",
                    description="Add a file"
                )
            ]
        )
        action_row = ActionRow(add_select_menu) 
        self.add_item(action_row)


class MessageBuilder(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot


    @app_commands.command(
        name="message-builder"
    )
    @app_commands.checks.has_permission(administrator=True)
    @app_commands.guild_only()
    async def cv2_message_builder(self, i: discord.Interaction):
        view = CV2BuilderUI()
        await i.response.send_message(
            view=view,
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(bot)