from typing import Any

from lfx.base.prompts.api_utils import process_prompt_template
from lfx.custom.custom_component.component import Component
from lfx.inputs.input_mixin import FieldTypes
from lfx.inputs.inputs import DefaultPromptField, TabInput
from lfx.io import MessageTextInput, Output, PromptInput
from lfx.schema.dotdict import dotdict
from lfx.schema.message import Message
from lfx.template.utils import update_template_values
from lfx.utils.mustache_security import validate_mustache_template


class PromptComponent(Component):
    display_name: str = "Prompt"
    description: str = "Create a prompt template with dynamic variables."
    documentation: str = "https://docs.langflow.org/components-prompts"
    icon = "prompts"
    trace_type = "prompt"
    name = "Prompt"
    priority = 0  # Set priority to 0 to make it appear first

    inputs = [
        TabInput(
            name="mode",
            display_name="Mode",
            options=["{variable}", "{{variable}}"],
            value="{variable}",
            info="Choose variable syntax for your template.",
            real_time_refresh=True,
        ),
        PromptInput(name="template", display_name="Template"),
        MessageTextInput(
            name="tool_placeholder",
            display_name="Tool Placeholder",
            tool_mode=True,
            advanced=True,
            info="A placeholder input for tool mode.",
        ),
    ]

    outputs = [
        Output(display_name="Prompt", name="prompt", method="build_prompt"),
    ]

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        """Update the template field type based on the selected mode."""
        if field_name == "mode":
            # Change the template field type based on mode
            is_mustache = field_value == "{{variable}}"
            if is_mustache:
                build_config["template"]["type"] = FieldTypes.MUSTACHE_PROMPT.value
            else:
                build_config["template"]["type"] = FieldTypes.PROMPT.value

            # Re-process the template to update variables when mode changes
            template_value = build_config.get("template", {}).get("value", "")
            if template_value:
                # Ensure custom_fields is properly initialized
                if "custom_fields" not in build_config:
                    build_config["custom_fields"] = {}

                # Clean up fields from the OLD mode before processing with NEW mode
                # This ensures we don't keep fields with wrong syntax even if validation fails
                old_custom_fields = build_config["custom_fields"].get("template", [])
                for old_field in list(old_custom_fields):
                    # Remove the field from custom_fields and template
                    if old_field in old_custom_fields:
                        old_custom_fields.remove(old_field)
                    build_config.pop(old_field, None)

                # Try to process template with new mode to add new variables
                # If validation fails, at least we cleaned up old fields
                try:
                    # Validate mustache templates for security
                    if is_mustache:
                        validate_mustache_template(template_value)

                    # Re-process template with new mode to add new variables
                    _ = process_prompt_template(
                        template=template_value,
                        name="template",
                        custom_fields=build_config["custom_fields"],
                        frontend_node_template=build_config,
                        is_mustache=is_mustache,
                    )
                except ValueError:
                    # If validation fails, we still updated the mode and cleaned old fields
                    # User will see error when they try to save
                    pass
        return build_config

    async def build_prompt(self) -> Message:
        mode = self.mode if hasattr(self, "mode") else "{variable}"
        template_format = "mustache" if mode == "{{variable}}" else "f-string"
        prompt = await Message.from_template_and_variables(template_format=template_format, **self._attributes)
        self.status = prompt.text
        return prompt

    def _update_template(self, frontend_node: dict):
        prompt_template = frontend_node["template"]["template"]["value"]
        mode = frontend_node["template"].get("mode", {}).get("value", "{variable}")
        is_mustache = mode == "{{variable}}"

        try:
            # Validate mustache templates for security
            if is_mustache:
                validate_mustache_template(prompt_template)

            custom_fields = frontend_node["custom_fields"]
            frontend_node_template = frontend_node["template"]
            _ = process_prompt_template(
                template=prompt_template,
                name="template",
                custom_fields=custom_fields,
                frontend_node_template=frontend_node_template,
                is_mustache=is_mustache,
            )
        except ValueError:
            # If validation fails, don't add variables but allow component to be created
            pass
        return frontend_node

    async def update_frontend_node(self, new_frontend_node: dict, current_frontend_node: dict):
        """This function is called after the code validation is done."""
        frontend_node = await super().update_frontend_node(new_frontend_node, current_frontend_node)
        template = frontend_node["template"]["template"]["value"]
        mode = frontend_node["template"].get("mode", {}).get("value", "{variable}")
        is_mustache = mode == "{{variable}}"

        try:
            # Validate mustache templates for security
            if is_mustache:
                validate_mustache_template(template)

            # Kept it duplicated for backwards compatibility
            _ = process_prompt_template(
                template=template,
                name="template",
                custom_fields=frontend_node["custom_fields"],
                frontend_node_template=frontend_node["template"],
                is_mustache=is_mustache,
            )
        except ValueError:
            # If validation fails, don't add variables but allow component to be updated
            pass
        # Now that template is updated, we need to grab any values that were set in the current_frontend_node
        # and update the frontend_node with those values
        update_template_values(new_template=frontend_node, previous_template=current_frontend_node["template"])
        return frontend_node

    def _get_fallback_input(self, **kwargs):
        return DefaultPromptField(**kwargs)
