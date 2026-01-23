# 🎬 Demo Configuration File
# Customize the SynapseFlow Multi-Agent DDA Demo

import os
from typing import Dict, Any

class DemoConfig:
    """Configuration for the SynapseFlow Multi-Agent DDA Demo."""
    
    # ============================================================================
    # DEMO BEHAVIOR
    # ============================================================================
    
    # Demo timing and flow
    DEMO_AUTO_ADVANCE = False          # Auto-advance between demos
    DEMO_DELAY_BETWEEN_STEPS = 1.0    # Seconds between step transitions
    SHOW_PROGRESS_BARS = True          # Display progress indicators
    
    # Interactive elements
    ENABLE_USER_INPUT = True           # Allow user to select DDA files
    DEFAULT_DDA_FILE = "crohns_disease_dda.md"  # Pre-selected file
    SKIP_DDA_SELECTION = False         # Skip file selection (use default)
    
    # ============================================================================
    # DISPLAY AND OUTPUT
    # ============================================================================
    
    # Console appearance
    ENABLE_COLORS = True               # Use colored output
    ENABLE_EMOJIS = True               # Use emoji indicators
    ENABLE_ANIMATIONS = False          # Simple text animations
    
    # Output detail level
    VERBOSE_OUTPUT = True              # Show detailed information
    SHOW_DEBUG_INFO = False            # Display debug messages
    SHOW_TIMING_INFO = True            # Show execution times
    
    # ============================================================================
    # KNOWLEDGE GRAPH CONFIGURATION
    # ============================================================================
    
    # Entity creation
    MAX_ENTITIES_TO_SHOW = 5           # Max entities displayed in sample
    MAX_RELATIONSHIPS_TO_SHOW = 5      # Max relationships displayed
    CREATE_SAMPLE_RELATIONSHIPS = True  # Create demo relationships
    
    # Relationship types
    DEFAULT_RELATIONSHIP_TYPE = "RELATES_TO"
    RELATIONSHIP_PROPERTIES = {
        "source": "dda_processing",
        "demo": True
    }
    
    # ============================================================================
    # AGENT CONFIGURATION
    # ============================================================================
    
    # Agent behavior
    AGENT_PROCESSING_DELAY = 0.5       # Simulate processing time
    SHOW_AGENT_MESSAGES = True         # Display agent communication
    ENABLE_ESCALATION_DEMO = True      # Show escalation workflows
    
    # Mock agent responses
    MOCK_AGENT_SUCCESS_RATE = 1.0      # Success rate for mock operations
    MOCK_VALIDATION_SUCCESS_RATE = 1.0 # Validation success rate
    MOCK_CONFLICT_DETECTION = True     # Enable conflict detection demo
    
    # ============================================================================
    # EVENT SYSTEM CONFIGURATION
    # ============================================================================
    
    # Event simulation
    SIMULATE_EVENT_PUBLISHING = True   # Show event publishing
    MAX_EVENTS_TO_SHOW = 3            # Maximum events displayed
    EVENT_DETAIL_LEVEL = "summary"     # "summary", "detailed", "minimal"
    
    # ============================================================================
    # VALIDATION AND TESTING
    # ============================================================================
    
    # Validation settings
    VALIDATE_ALL_ENTITIES = True       # Run validation on all entities
    SHOW_VALIDATION_DETAILS = True     # Display validation results
    ENABLE_CONFLICT_TESTING = True     # Test conflict detection
    
    # Testing mode
    TEST_MODE = False                  # Enable testing features
    SKIP_ERRORS = False                # Continue on errors
    GENERATE_TEST_REPORTS = False      # Create test result files
    
    # ============================================================================
    # CUSTOMIZATION
    # ============================================================================
    
    # Custom DDA processing
    CUSTOM_ENTITY_EXTRACTORS = {}      # Custom entity extraction rules
    CUSTOM_RELATIONSHIP_RULES = {}     # Custom relationship creation rules
    
    # Custom agent behaviors
    CUSTOM_AGENT_RESPONSES = {}        # Override mock agent responses
    CUSTOM_VALIDATION_RULES = {}       # Custom validation logic
    
    # ============================================================================
    # PRESENTATION MODE
    # ============================================================================
    
    # Presentation settings
    PRESENTATION_MODE = False          # Enable presentation optimizations
    AUTO_PAUSE_AT_HIGHLIGHTS = False   # Pause at key moments
    HIGHLIGHT_KEY_FEATURES = True      # Emphasize important aspects
    
    # Audience-specific settings
    AUDIENCE_TYPE = "technical"        # "technical", "business", "mixed"
    TECHNICAL_DETAIL_LEVEL = "medium"  # "basic", "medium", "advanced"
    
    # ============================================================================
    # OUTPUT AND LOGGING
    # ============================================================================
    
    # Logging configuration
    ENABLE_LOGGING = True              # Enable demo logging
    LOG_LEVEL = "INFO"                 # "DEBUG", "INFO", "WARNING", "ERROR"
    LOG_TO_FILE = False                # Save logs to file
    LOG_FILE_PATH = "demo.log"         # Log file location
    
    # Report generation
    GENERATE_DEMO_REPORT = False       # Create demo summary report
    REPORT_FORMAT = "markdown"         # "markdown", "html", "json"
    REPORT_OUTPUT_PATH = "demo_report.md"
    
    # ============================================================================
    # ADVANCED FEATURES
    # ============================================================================
    
    # Performance monitoring
    ENABLE_PERFORMANCE_MONITORING = False  # Track execution times
    SHOW_MEMORY_USAGE = False          # Display memory consumption
    BENCHMARK_MODE = False             # Run performance benchmarks
    
    # Integration testing
    ENABLE_INTEGRATION_TESTS = False   # Run integration test suite
    TEST_EXTERNAL_SERVICES = False     # Test external dependencies
    
    # ============================================================================
    # ENVIRONMENT OVERRIDES
    # ============================================================================
    
    @classmethod
    def from_environment(cls) -> 'DemoConfig':
        """Create config from environment variables."""
        config = cls()
        
        # Override with environment variables
        for key, value in config.__dict__.items():
            env_key = f"DEMO_{key}"
            if env_key in os.environ:
                env_value = os.environ[env_key]
                # Convert string values to appropriate types
                if isinstance(value, bool):
                    config.__dict__[key] = env_value.lower() in ('true', '1', 'yes')
                elif isinstance(value, int):
                    config.__dict__[key] = int(env_value)
                elif isinstance(value, float):
                    config.__dict__[key] = float(env_value)
                else:
                    config.__dict__[key] = env_value
        
        return config
    
    @classmethod
    def presentation_mode(cls) -> 'DemoConfig':
        """Create config optimized for presentations."""
        config = cls()
        config.PRESENTATION_MODE = True
        config.AUTO_ADVANCE = False
        config.SHOW_PROGRESS_BARS = True
        config.ENABLE_COLORS = True
        config.ENABLE_EMOJIS = True
        config.VERBOSE_OUTPUT = False
        config.SHOW_DEBUG_INFO = False
        config.AGENT_PROCESSING_DELAY = 1.0
        config.HIGHLIGHT_KEY_FEATURES = True
        return config
    
    @classmethod
    def testing_mode(cls) -> 'DemoConfig':
        """Create config optimized for testing."""
        config = cls()
        config.TEST_MODE = True
        config.SKIP_ERRORS = True
        config.GENERATE_TEST_REPORTS = True
        config.ENABLE_LOGGING = True
        config.LOG_LEVEL = "DEBUG"
        config.ENABLE_PERFORMANCE_MONITORING = True
        return config
    
    @classmethod
    def development_mode(cls) -> 'DemoConfig':
        """Create config optimized for development."""
        config = cls()
        config.VERBOSE_OUTPUT = True
        config.SHOW_DEBUG_INFO = True
        config.ENABLE_LOGGING = True
        config.LOG_LEVEL = "DEBUG"
        config.SKIP_ERRORS = False
        config.ENABLE_PERFORMANCE_MONITORING = True
        return config

# ============================================================================
# PRESET CONFIGURATIONS
# ============================================================================

# Quick access to common configurations
PRESENTATION_CONFIG = DemoConfig.presentation_mode()
TESTING_CONFIG = DemoConfig.testing_mode()
DEVELOPMENT_CONFIG = DemoConfig.development_mode()
DEFAULT_CONFIG = DemoConfig.from_environment()

# ============================================================================
# USAGE EXAMPLES
# ============================================================================

if __name__ == "__main__":
    # Example: Load configuration
    config = DemoConfig.from_environment()
    
    # Example: Use presentation mode
    if config.PRESENTATION_MODE:
        config = DemoConfig.presentation_mode()
    
    # Example: Customize for specific audience
    if config.AUDIENCE_TYPE == "business":
        config.TECHNICAL_DETAIL_LEVEL = "basic"
        config.VERBOSE_OUTPUT = False
    
    print("🎬 Demo Configuration Loaded:")
    print(f"   Presentation Mode: {config.PRESENTATION_MODE}")
    print(f"   Verbose Output: {config.VERBOSE_OUTPUT}")
    print(f"   Auto Advance: {config.AUTO_ADVANCE}")
    print(f"   Colors Enabled: {config.ENABLE_COLORS}")
    print(f"   Emojis Enabled: {config.ENABLE_EMOJIS}")
