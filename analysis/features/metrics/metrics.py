from pydantic import BaseModel

class Metrics(BaseModel):
    """Base class for all metric models.
    
    Provides utility functions for adding, subtracting, and taking absolute values of models.
    """

    def __add__[T: Metrics](self: T, other: T) -> T:
        """Add corresponding fields from two models of the same type."""
        if not isinstance(other, type(self)):
            raise TypeError(f"Cannot add {type(self).__name__} with {type(other).__name__}")
        
        new_values = {}
        for field_name in self.model_fields:
            self_value = getattr(self, field_name)
            other_value = getattr(other, field_name)
            
            # Skip None values
            if self_value is None or other_value is None:
                new_values[field_name] = None
                continue
                
            try:
                new_values[field_name] = self_value + other_value
            except TypeError as e:
                raise TypeError(f"Cannot add field '{field_name}': {str(e)}")
        
        return type(self)(**new_values)

    def __sub__[T: Metrics](self: T, other: T) -> T:
        """Subtract corresponding fields from two models of the same type."""
        if not isinstance(other, type(self)):
            raise TypeError(f"Cannot subtract {type(self).__name__} with {type(other).__name__}")
        
        new_values = {}
        for field_name in self.model_fields:
            self_value = getattr(self, field_name)
            other_value = getattr(other, field_name)
            
            # Skip None values
            if self_value is None or other_value is None:
                new_values[field_name] = None
                continue
                
            try:
                new_values[field_name] = self_value - other_value
            except TypeError as e:
                raise TypeError(f"Cannot subtract field '{field_name}': {str(e)}")
        
        return type(self)(**new_values)

    def __abs__[T: Metrics](self: T) -> T:
        """Return a new model with absolute values of all fields."""
        new_values = {}
        for field_name in self.model_fields:
            value = getattr(self, field_name)
            
            # Skip None values
            if value is None:
                new_values[field_name] = None
                continue
                
            try:
                new_values[field_name] = abs(value)
            except TypeError as e:
                raise TypeError(f"Cannot take absolute value of field '{field_name}': {str(e)}")
        
        return type(self)(**new_values)

    def to_dict(self, prefix: str | None = None, suffix: str | None = None) -> dict[str, int | float]:
        """Convert model to dictionary."""
        def update_field_name(field_name: str, separator: str = "/") -> str:
            if prefix is not None:
                field_name = f"{prefix}{separator}{field_name}"
            if suffix is not None:
                field_name = f"{field_name}{separator}{suffix}"
            return field_name
        
        return {
            update_field_name(field_name): getattr(self, field_name)
            for field_name in self.model_fields
        }