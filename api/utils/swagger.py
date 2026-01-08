from drf_yasg.inspectors import SwaggerAutoSchema


ACTION_KEYS = {
    "list",
    "read",
    "create",
    "update",
    "partial_update",
    "delete",
}


class GroupedSwaggerAutoSchema(SwaggerAutoSchema):
    def get_tags(self, operation_keys=None):
        op_keys = list(operation_keys or self.operation_keys or [])
        if op_keys:
            if op_keys[-1] in ACTION_KEYS:
                op_keys = op_keys[:-1]

            if op_keys and op_keys[0] in {"desktop", "mobile"}:
                if op_keys[0] == "mobile":
                    if len(op_keys) > 1 and op_keys[1] in {"main-category", "sub-category"}:
                        return ["grievance"]
                    if len(op_keys) > 1:
                        return [op_keys[1]]
                    return ["mobile"]

                if len(op_keys) > 1:
                    return [op_keys[1]]
                return ["desktop"]

            if op_keys:
                return [op_keys[0]]

        return super().get_tags(operation_keys=operation_keys)
