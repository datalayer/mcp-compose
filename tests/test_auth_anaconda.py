"""
Tests for Anaconda authentication.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from mcp_compose.providers.auth_anaconda import AnacondaAuthenticator, create_anaconda_authenticator
from mcp_compose.auth import AuthType, InvalidCredentialsError


class TestAnacondaAuthenticator:
    """Test Anaconda authenticator."""
    
    def test_init_default_domain(self):
        """Test initialization with default domain."""
        with patch('anaconda_auth.token.TokenInfo'):
            auth = AnacondaAuthenticator()
            assert auth.domain == "anaconda.com"
            assert auth.auth_type == AuthType.API_KEY
    
    def test_init_custom_domain(self):
        """Test initialization with custom domain."""
        with patch('anaconda_auth.token.TokenInfo'):
            auth = AnacondaAuthenticator(domain="custom.anaconda.com")
            assert auth.domain == "custom.anaconda.com"
    
    def test_init_missing_anaconda_auth(self):
        """Test initialization fails without anaconda-auth package."""
        with patch('anaconda_auth.token.TokenInfo', side_effect=ImportError):
            with pytest.raises(ImportError) as exc_info:
                AnacondaAuthenticator()
            assert "anaconda-auth is required" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_authenticate_success(self):
        """Test successful authentication."""
        # Mock TokenInfo class
        mock_token_info = MagicMock()
        mock_token_info.get_access_token.return_value = "valid_access_token"
        mock_token_info.username = "test_user"
        
        mock_token_info_class = Mock(return_value=mock_token_info)
        
        with patch('anaconda_auth.token.TokenInfo', mock_token_info_class):
            auth = AnacondaAuthenticator()
            
            # Authenticate
            context = await auth.authenticate({"token": "test_token"})
            
            # Verify
            assert context.user_id == "test_user"
            assert context.auth_type == AuthType.API_KEY
            assert context.token == "test_token"
            assert "*" in context.scopes
            assert context.metadata["domain"] == "anaconda.com"
            assert context.metadata["access_token"] == "valid_access_token"
            
            # Verify TokenInfo was called correctly
            mock_token_info_class.assert_called_once_with(
                domain="anaconda.com",
                api_key="test_token"
            )
    
    @pytest.mark.asyncio
    async def test_authenticate_with_api_key(self):
        """Test authentication using api_key field."""
        mock_token_info = MagicMock()
        mock_token_info.get_access_token.return_value = "access_token"
        mock_token_info.username = "test_user"
        
        with patch('anaconda_auth.token.TokenInfo', return_value=mock_token_info):
            auth = AnacondaAuthenticator()
            context = await auth.authenticate({"api_key": "test_key"})
            
            assert context.token == "test_key"
            assert context.user_id == "test_user"
    
    @pytest.mark.asyncio
    async def test_authenticate_no_token(self):
        """Test authentication fails without token."""
        with patch('anaconda_auth.token.TokenInfo'):
            auth = AnacondaAuthenticator()
            
            with pytest.raises(InvalidCredentialsError) as exc_info:
                await auth.authenticate({})
            
            assert "token not provided" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_authenticate_invalid_token(self):
        """Test authentication fails with invalid token."""
        mock_token_info = MagicMock()
        mock_token_info.get_access_token.return_value = None
        
        with patch('anaconda_auth.token.TokenInfo', return_value=mock_token_info):
            auth = AnacondaAuthenticator()
            
            with pytest.raises(InvalidCredentialsError) as exc_info:
                await auth.authenticate({"token": "invalid_token"})
            
            assert "Invalid Anaconda token" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_authenticate_exception(self):
        """Test authentication handles exceptions."""
        with patch('anaconda_auth.token.TokenInfo', side_effect=Exception("API error")):
            auth = AnacondaAuthenticator()
            
            with pytest.raises(InvalidCredentialsError) as exc_info:
                await auth.authenticate({"token": "test_token"})
            
            assert "Anaconda authentication failed" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_validate_valid_context(self):
        """Test validation of valid context."""
        mock_token_info = MagicMock()
        mock_token_info.get_access_token.return_value = "access_token"
        mock_token_info.username = "test_user"
        
        with patch('anaconda_auth.token.TokenInfo', return_value=mock_token_info):
            auth = AnacondaAuthenticator()
            
            # Create context
            context = await auth.authenticate({"token": "valid_token"})
            
            # Validate
            is_valid = await auth.validate(context)
            assert is_valid is True
    
    @pytest.mark.asyncio
    async def test_validate_invalid_context(self):
        """Test validation of invalid context."""
        mock_token_info_valid = MagicMock()
        mock_token_info_valid.get_access_token.return_value = "access_token"
        mock_token_info_valid.username = "test_user"
        
        mock_token_info_invalid = MagicMock()
        mock_token_info_invalid.get_access_token.side_effect = Exception("Invalid")
        
        with patch('anaconda_auth.token.TokenInfo') as mock_class:
            # First call returns valid, second returns invalid
            mock_class.side_effect = [mock_token_info_valid, mock_token_info_invalid]
            
            auth = AnacondaAuthenticator()
            context = await auth.authenticate({"token": "valid_token"})
            
            # Now validate with expired token
            is_valid = await auth.validate(context)
            assert is_valid is False
    
    def test_get_user_from_token_username(self):
        """Test extracting username from token."""
        with patch('anaconda_auth.token.TokenInfo'):
            auth = AnacondaAuthenticator()
            
            mock_token = Mock()
            mock_token.username = "test_user"
            
            user_id = auth._get_user_from_token(mock_token)
            assert user_id == "test_user"
    
    def test_get_user_from_token_user_id(self):
        """Test extracting user_id from token."""
        with patch('anaconda_auth.token.TokenInfo'):
            auth = AnacondaAuthenticator()
            
            mock_token = Mock()
            mock_token.username = None
            mock_token.user_id = 12345
            
            user_id = auth._get_user_from_token(mock_token)
            assert user_id == "12345"
    
    def test_get_user_from_token_email(self):
        """Test extracting email from token."""
        with patch('anaconda_auth.token.TokenInfo'):
            auth = AnacondaAuthenticator()
            
            mock_token = Mock()
            mock_token.username = None
            mock_token.user_id = None
            mock_token.email = "test@example.com"
            
            user_id = auth._get_user_from_token(mock_token)
            assert user_id == "test@example.com"
    
    def test_get_user_from_token_fallback(self):
        """Test fallback user ID."""
        with patch('anaconda_auth.token.TokenInfo'):
            auth = AnacondaAuthenticator()
            
            mock_token = Mock()
            mock_token.username = None
            mock_token.user_id = None
            mock_token.email = None
            
            user_id = auth._get_user_from_token(mock_token)
            assert user_id == "anaconda_user"


def test_create_anaconda_authenticator():
    """Test factory function."""
    with patch('anaconda_auth.token.TokenInfo'):
        auth = create_anaconda_authenticator(domain="test.com")
        assert isinstance(auth, AnacondaAuthenticator)
        assert auth.domain == "test.com"


def test_create_anaconda_authenticator_defaults():
    """Test factory function with defaults."""
    with patch('anaconda_auth.token.TokenInfo'):
        auth = create_anaconda_authenticator()
        assert isinstance(auth, AnacondaAuthenticator)
        assert auth.domain == "anaconda.com"
