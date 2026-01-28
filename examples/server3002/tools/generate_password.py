"""
Generate a secure password with customizable options.
No authentication required - public tool.
"""

import json
import math
import random
import string


def generate_password(request: dict) -> dict:
    """Generate a secure password with customizable length and character sets."""
    # Handle different parameter structures
    params_data = {}

    params = request.get("params", {})
    arguments = params.get("arguments")

    if arguments:
        if isinstance(arguments, str):
            # Gopher-orch sends arguments as JSON string
            try:
                params_data = json.loads(arguments)
            except json.JSONDecodeError:
                pass
        elif isinstance(arguments, dict):
            # Direct calls send arguments as object
            params_data = arguments
    else:
        params_data = params

    # Extract parameters with defaults
    length = params_data.get("length", 16)
    include_uppercase = params_data.get("includeUppercase", True)
    include_lowercase = params_data.get("includeLowercase", True)
    include_numbers = params_data.get("includeNumbers", True)
    include_symbols = params_data.get("includeSymbols", True)
    exclude_similar = params_data.get("excludeSimilar", False)

    # Validate length
    if length < 8 or length > 128:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error: Password length must be between 8 and 128 characters.",
                }
            ],
            "isError": True,
        }

    # Character sets
    uppercase = string.ascii_uppercase
    lowercase = string.ascii_lowercase
    numbers = string.digits
    symbols = "!@#$%^&*()_+-=[]{}|;:,.<>?"

    # Exclude similar characters if requested
    if exclude_similar:
        uppercase = uppercase.replace("O", "")
        lowercase = lowercase.replace("l", "")
        numbers = numbers.replace("0", "").replace("1", "")
        symbols = symbols.replace("|", "")

    # Build character pool
    char_pool = ""
    required_chars = []

    if include_uppercase:
        char_pool += uppercase
        required_chars.append(random.choice(uppercase))
    if include_lowercase:
        char_pool += lowercase
        required_chars.append(random.choice(lowercase))
    if include_numbers:
        char_pool += numbers
        required_chars.append(random.choice(numbers))
    if include_symbols:
        char_pool += symbols
        required_chars.append(random.choice(symbols))

    # Ensure at least one character set is selected
    if not char_pool:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error: At least one character set must be included.",
                }
            ],
            "isError": True,
        }

    # Generate password
    password = list(required_chars)

    # Fill the rest with random characters
    for _ in range(length - len(required_chars)):
        password.append(random.choice(char_pool))

    # Shuffle the password to randomize the position of required characters
    random.shuffle(password)
    password = "".join(password)

    # Calculate password strength
    pool_size = 0
    if include_uppercase:
        pool_size += 26
    if include_lowercase:
        pool_size += 26
    if include_numbers:
        pool_size += 10
    if include_symbols:
        pool_size += len(symbols)

    entropy = math.log2(pool_size ** length)

    if entropy < 40:
        strength_text = "Weak"
    elif entropy < 60:
        strength_text = "Fair"
    elif entropy < 80:
        strength_text = "Good"
    elif entropy < 100:
        strength_text = "Strong"
    else:
        strength_text = "Very Strong"

    # Build settings summary
    settings = []
    if include_uppercase:
        settings.append("Uppercase")
    if include_lowercase:
        settings.append("Lowercase")
    if include_numbers:
        settings.append("Numbers")
    if include_symbols:
        settings.append("Symbols")
    if exclude_similar:
        settings.append("No Similar Chars")

    return {
        "content": [
            {
                "type": "text",
                "text": (
                    f"Generated Password:\n\n"
                    f"🔐 {password}\n\n"
                    f"Settings:\n"
                    f"• Length: {length} characters\n"
                    f"• Character types: {', '.join(settings)}\n"
                    f"• Strength: {strength_text}\n"
                    f"• Entropy: {entropy:.1f} bits\n\n"
                    f"💡 Tip: Store this password securely and don't reuse it for multiple accounts."
                ),
            }
        ],
    }
