main :: IO ()
main = do
    _ <- getLine
    mx :: Int <- maximum <$> map read <$> words <$> getLine
    putStrLn $ show mx
