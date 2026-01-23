"""Tests for the RabbitMQ event bus."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone
from src.infrastructure.event_bus.rabbitmq_event_bus import RabbitMQEventBus
from src.domain.event import KnowledgeEvent


class TestRabbitMQEventBus:
    """Test cases for RabbitMQEventBus."""
    
    @pytest.fixture
    def mock_connection(self):
        """Create a mock aio_pika connection."""
        mock = Mock()
        mock.channel = AsyncMock()
        mock.channel.declare_queue = AsyncMock()
        mock.channel.declare_exchange = AsyncMock()
        mock.channel.publish = AsyncMock()
        mock.channel.consume = AsyncMock()
        return mock
    
    @pytest.fixture
    def event_bus(self, mock_connection):
        """Create a RabbitMQEventBus instance for testing."""
        with patch('src.infrastructure.event_bus.rabbitmq_event_bus.connect_robust') as mock_connect:
            mock_connect.return_value = mock_connection
            return RabbitMQEventBus("amqp://localhost")
    
    @pytest.mark.asyncio
    async def test_initialization(self, event_bus):
        """Test that event bus initializes correctly."""
        assert event_bus.connection_url == "amqp://localhost"
        assert event_bus.connection is None
        assert event_bus.channel is None
    
    @pytest.mark.asyncio
    async def test_connect(self, event_bus, mock_connection):
        """Test connecting to RabbitMQ."""
        await event_bus.connect()
        
        assert event_bus.connection is not None
        assert event_bus.channel is not None
    
    @pytest.mark.asyncio
    async def test_disconnect(self, event_bus, mock_connection):
        """Test disconnecting from RabbitMQ."""
        await event_bus.connect()
        await event_bus.disconnect()
        
        assert event_bus.connection is None
        assert event_bus.channel is None
    
    @pytest.mark.asyncio
    async def test_publish_event(self, event_bus, mock_connection):
        """Test publishing an event."""
        await event_bus.connect()
        
        event = KnowledgeEvent(
            action="test_event",
            data={"key": "value"},
            role="data_architect"
        )
        
        await event_bus.publish(event)
        
        # Verify event was published
        event_bus.channel.publish.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_subscribe_to_queue(self, event_bus, mock_connection):
        """Test subscribing to a queue."""
        await event_bus.connect()
        
        callback = Mock()
        await event_bus.subscribe("test_queue", callback)
        
        # Verify queue was declared
        event_bus.channel.declare_queue.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_consume_messages(self, event_bus, mock_connection):
        """Test consuming messages from a queue."""
        await event_bus.connect()
        
        # Mock message consumption
        mock_message = Mock()
        mock_message.body = b'{"event_type": "test", "data": {}}'
        mock_message.ack = AsyncMock()
        
        event_bus.channel.consume.return_value = [mock_message]
        
        callback = Mock()
        await event_bus.subscribe("test_queue", callback)
        
        # Verify message was consumed
        callback.assert_called_once()
        mock_message.ack.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_error_handling(self, event_bus, mock_connection):
        """Test error handling during operations."""
        # Mock connection failure
        with patch('src.infrastructure.event_bus.rabbitmq_event_bus.connect_robust') as mock_connect:
            mock_connect.side_effect = Exception("Connection failed")
            
            with pytest.raises(Exception):
                await event_bus.connect()
    
    @pytest.mark.asyncio
    async def test_reconnection(self, event_bus, mock_connection):
        """Test automatic reconnection on failure."""
        await event_bus.connect()
        
        # Simulate connection loss
        event_bus.connection = None
        event_bus.channel = None
        
        # Attempt to publish (should trigger reconnection)
        event = KnowledgeEvent(
            action="test_event",
            data={"key": "value"},
            role="data_architect"
        )
        
        await event_bus.publish(event)
        
        # Verify reconnection was attempted
        assert event_bus.connection is not None
        assert event_bus.channel is not None
