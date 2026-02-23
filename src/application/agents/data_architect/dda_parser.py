from abc import ABC, abstractmethod
from typing import List
from domain.dda_models import DDADocument


class DDAParser(ABC):
    """Abstract interface for DDA document parsers."""
    
    @abstractmethod
    async def parse(self, file_path: str) -> DDADocument:
        """Parse a DDA document and return structured data."""
        pass
    
    @abstractmethod
    def supports_format(self, file_path: str) -> bool:
        """Check if this parser supports the given file format."""
        pass
    
    @abstractmethod
    def get_supported_formats(self) -> List[str]:
        """Return list of supported file formats."""
        pass


class DDAParserFactory:
    """Factory for creating appropriate DDA parsers based on file format."""
    
    def __init__(self):
        self._parsers: List[DDAParser] = []
    
    def register_parser(self, parser: DDAParser) -> None:
        """Register a parser with the factory."""
        self._parsers.append(parser)
    
    def get_parser(self, file_path: str) -> DDAParser:
        """Get the appropriate parser for the given file."""
        for parser in self._parsers:
            if parser.supports_format(file_path):
                return parser
        
        # Return a fallback parser if no specific parser is found
        return self._get_fallback_parser()
    
    def _get_fallback_parser(self) -> DDAParser:
        """Get a fallback parser for unsupported formats."""
        # For now, return the text parser as fallback
        # This will be implemented when we create the text parser
        raise NotImplementedError("Fallback parser not yet implemented")
    
    def get_supported_formats(self) -> List[str]:
        """Get all supported file formats."""
        formats = []
        for parser in self._parsers:
            formats.extend(parser.get_supported_formats())
        return list(set(formats))  # Remove duplicates 