from pisek.config.config_types import ValidatorType
from pisek.task_jobs.validator.validator_base import ValidatorJob
from pisek.task_jobs.validator.simple_validator import Simple0Validate, Simple42Validate

VALIDATORS: dict[ValidatorType, type[ValidatorJob]] = {
    ValidatorType.simple_0: Simple0Validate,
    ValidatorType.simple_42: Simple42Validate,
}
