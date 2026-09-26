INSERT INTO users (
    user_id,
    line_user_id,
    display_name
)
VALUES (
    1,
    'test_line_user_001',
    'demo_player'
)
ON CONFLICT (user_id) DO NOTHING;
