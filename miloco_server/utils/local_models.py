# Copyright (C) 2025 Xiaomi Corporation
# This software may be used and distributed according to the terms of the Xiaomi Miloco License Agreement.

"""
Model purpose enumeration.
"""

import logging
from enum import Enum

from miloco_server.middleware.exceptions import ValidationException

logger = logging.getLogger(__name__)


class ModelPurpose(str, Enum):
    """Model purpose enumeration"""
    PLANNING = "planning"
    VISION_UNDERSTANDING = "vision_understanding"

    def __missing__(self, value):
        logger.error("Invalid model purpose: %s", value)
        raise ValidationException(f"Invalid model purpose: {value}")
