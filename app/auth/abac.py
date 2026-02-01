import yaml
import os

class ABACEngine:
    def __init__(self, policy_file):
        # Load policies from a YAML configuration file
        policy_path = os.path.join(os.getcwd(), policy_file)
        with open(policy_path, 'r') as f:
            data = yaml.safe_load(f)
        self.policies = data.get('policies', [])

    def evaluate_policy(self, request_context, resource, action):
        """
        Evaluate policies for a given request.
        
        :param request_context: A dict with attributes of the user/request.
                                e.g., { 'user_id': 'abc', 'role_type': 'client', 'authenticated': True }
        :param resource: The resource type being accessed (e.g., "products", "addresses").
        :param action: The requested action (e.g., "GET", "POST").
        :return: Boolean indicating if access is allowed.
        """
        # Go through each policy to see if one applies
        for policy in self.policies:
            # Check if the requested action is allowed under the policy
            if action not in policy.get('allowed_actions', []):
                continue

            # Check if resource type requirement is specified and doesn't match
            resource_types = policy.get('condition', {}).get('resource_type')
            if resource_types and resource not in resource_types:
                continue

            # For addresses, you might require an extra field like address_type
            if resource == "addresses":
                required_address_type = policy.get('condition', {}).get('address_type')
                if required_address_type:
                    # This field should be part of the resource object passed in
                    if resource.get('address_type') != required_address_type:
                        continue

            # Evaluate other conditions dynamically
            if not self._match_conditions(policy.get('condition', {}), request_context):
                continue

            # If all conditions match, allow the action
            return True

        # Default to deny if no policy grants access
        return False

    def _match_conditions(self, conditions, context):
        """
        Simple condition matcher. This will iterate through condition keys and ensure that the
        corresponding context value matches, allowing placeholders like {user.id}.
        """
        for key, expected in conditions.items():
            if key in ['resource_type', 'address_type']:
                # Already handled above
                continue
            actual = context.get(key)
            # If expected is a placeholder, resolve it from the context.
            if isinstance(expected, str) and expected.startswith('{') and expected.endswith('}'):
                placeholder = expected.strip('{}').split('.')
                # e.g., "user.id" -> first get user from context then id
                temp = context
                for part in placeholder:
                    temp = temp.get(part)
                    if temp is None:
                        break
                expected = temp
            if actual != expected:
                return False
        return True


# Example usage:
if __name__ == "__main__":
    # Assume your config file is at config/abac_policies.yaml
    engine = ABACEngine("config/abac_policies.yaml")
    
    # Sample request context for a registered client
    request_context = {
        "user_id": "user-123",
        "role_type": "client",
        "authenticated": True
    }
    
    # Simulated resource access request for a product
    resource = "products"
    action = "GET"

    if engine.evaluate_policy(request_context, resource, action):
        print("Access granted!")
    else:
        print("Access denied.")
