# Redis 实现 JWT 令牌拉黑功能：原理与实战

> 作者：一诺

## 前言

大家好，我是一诺。今天分享是一个 JWT 令牌安全管理问题。

当用户退出登录或账号出现安全问题时，我们往往无法立即让已颁发的 JWT 令牌失效。这个问题不仅影响用户体验，更可能带来严重的安全隐患。比如：

- 用户的 JWT 令牌通过 XSS 攻击或网络嗅探被恶意获取
- 系统检测到异常登录行为
- 用户主动报告账号安全问题

在这些情况下，我们需要一种机制能够立即撤销所有已颁发的令牌，防止进一步的未授权访问。经过实践，我发现使用 Redis 来实现令牌拉黑是一个既简单又高效的解决方案。

## 实现原理

Token 拉黑机制的核心思想很简单：

1. 维护一个"黑名单"，存储已被撤销的 token
2. 每次请求来临时，除了验证 token 的签名和过期时间外，还要检查它是否在黑名单中
3. 如果在黑名单中，则拒绝请求

听起来简单，但实际实现时需要考虑几个问题：

- 黑名单存储在哪里？
- 如何避免黑名单无限增长？
- 如何确保黑名单查询足够快，不影响性能？

这就是 Redis 派上用场的地方。

## 为什么选择 Redis？

Redis 作为一个内存数据库，具有以下优势：

1. **超高速查询**：毫秒级的读写性能
2. **键值过期机制**：可以设置键的过期时间，过期后自动删除
3. **原子操作**：保证并发情况下的数据一致性
4. **集群支持**：可扩展性强，适合高并发场景

这些特性使 Redis 成为实现 Token 黑名单的理想选择。

## 具体实现

下面让我们看看项目中的实际代码实现。

### 1. Redis 模块配置

首先，我们需要配置 Redis 连接。项目使用了 ioredis 客户端：

```typescript
@Module({
  imports: [ConfigModule, AppConfigModule],
  providers: [
    {
      provide: REDIS_CLIENT,
      inject: [AppConfigService],
      useFactory: async (configService: AppConfigService) => {
        const logger = new Logger("RedisModule");
        const redisConfig = configService.redis;

        logger.log(
          `正在连接Redis: ${redisConfig.host}:${redisConfig.port}, db: ${redisConfig.db}`
        );

        const client = new Redis({
          host: redisConfig.host,
          port: redisConfig.port,
          retryStrategy(times) {
            if (times > redisConfig.retryAttempts) {
              logger.error(
                `Redis连接重试次数超过限制: ${times}/${redisConfig.retryAttempts}，停止重试`
              );
              return null; // 停止重试
            }
            const delay = Math.min(times * redisConfig.retryDelay, 10000);
            logger.warn(
              `Redis连接失败，${delay}毫秒后重试 (${times}/${redisConfig.retryAttempts})`
            );
            return delay;
          },
        });

        // 监听连接事件
        client.on("connect", () => {
          logger.log("Redis连接已建立！");
        });

        client.on("ready", () => {
          logger.log("Redis连接就绪");
        });

        // 省略错误处理代码...

        return client;
      },
    },
  ],
  exports: [REDIS_CLIENT],
})
export class RedisModule {}
```

### 2. TokenBlacklistService 实现

这是整个机制的核心服务：

```typescript
@Injectable()
export class TokenBlacklistService {
  private readonly blacklistPrefix = "bl_token:";
  private readonly logger = new Logger(TokenBlacklistService.name);

  constructor(
    @Inject(REDIS_CLIENT) private readonly redis: Redis,
    private readonly jwtService: JwtService
  ) {}

  /**
   * 将token加入黑名单
   * @param token JWT令牌
   * @param userId 用户ID
   * @returns 操作结果
   */
  async addToBlacklist(token: string, userId: string): Promise<boolean> {
    if (!token) {
      this.logger.warn("尝试将空token加入黑名单");
      return false;
    }

    try {
      // 解析token获取过期时间
      const payload = this.jwtService.decode(token);
      if (!payload || typeof payload !== "object" || !payload.exp) {
        this.logger.warn("无效token格式，无法解析过期时间");
        return false;
      }

      // 计算剩余过期时间（秒）
      const currentTimestamp = Math.floor(Date.now() / 1000);
      const ttl = Math.max(0, payload.exp - currentTimestamp);

      // 如果token已过期，无需加入黑名单
      if (ttl <= 0) {
        this.logger.debug("token已过期，无需加入黑名单");
        return true;
      }

      // 使用token的哈希值作为key
      const tokenHash = this.hashToken(token);
      const tokenKey = `${this.blacklistPrefix}${tokenHash}`;

      await this.redis.set(tokenKey, userId, "EX", ttl);
      this.logger.debug(
        `Token已加入黑名单, 用户ID: ${userId}, 过期时间: ${ttl}秒`
      );

      return true;
    } catch (error) {
      const err = error as Error;
      this.logger.error(`将token加入黑名单失败: ${err.message}`);
      return false;
    }
  }

  /**
   * 检查token是否在黑名单中
   * @param token JWT令牌
   * @returns 是否在黑名单中
   */
  async isBlacklisted(token: string): Promise<boolean> {
    if (!token) {
      return false;
    }

    try {
      const tokenHash = this.hashToken(token);
      const tokenKey = `${this.blacklistPrefix}${tokenHash}`;

      const exists = await this.redis.exists(tokenKey);
      return exists === 1;
    } catch (error) {
      const err = error as Error;
      this.logger.error(`检查token黑名单状态失败: ${err.message}`);
      // 发生错误时，默认允许请求通过，避免系统锁死
      return false;
    }
  }

  /**
   * 对token进行哈希处理，避免存储原始token
   * @param token JWT令牌
   * @returns token的哈希值
   */
  private hashToken(token: string): string {
    // 使用SHA-256哈希算法处理token
    return crypto.createHash("sha256").update(token).digest("hex");
  }
}
```

### 3. JWT 守卫集成

每个受保护的请求都会经过 JWT 守卫，我们在这里集成黑名单检查：

```typescript
@Injectable()
export class JwtAuthGuard extends AuthGuard("jwt") {
  private readonly logger = new Logger(JwtAuthGuard.name);

  constructor(
    private reflector: Reflector,
    private tokenBlacklistService: TokenBlacklistService
  ) {
    super();
  }

  async canActivate(context: ExecutionContext): Promise<boolean> {
    // 检查是否标记为公共接口
    const isPublic = this.reflector.getAllAndOverride<boolean>(IS_PUBLIC_KEY, [
      context.getHandler(),
      context.getClass(),
    ]);

    if (isPublic) {
      return true;
    }

    try {
      // 执行标准JWT验证
      const canActivate = super.canActivate(context);
      const isValidJwt =
        canActivate instanceof Observable
          ? await firstValueFrom(canActivate)
          : await Promise.resolve(canActivate);

      // 如果JWT验证通过，检查token是否在黑名单中
      if (isValidJwt) {
        const request = context.switchToHttp().getRequest();
        const token = this.extractTokenFromHeader(request);

        // 如果找到token，检查是否在黑名单中
        if (token) {
          const isBlacklisted = await this.tokenBlacklistService.isBlacklisted(
            token
          );
          if (isBlacklisted) {
            this.logger.debug(`令牌已被撤销: ${this.maskToken(token)}`);
            throw new UnauthorizedException({
              code: ResponseCode.TOKEN_REVOKED,
              message: "登录已失效，请重新登录 TOKEN_REVOKED",
            });
          }
        }
      }

      return isValidJwt;
    } catch (error) {
      // 错误处理逻辑...
    }
  }

  // 提取请求头中的token
  private extractTokenFromHeader(request: any): string | null {
    const authHeader = request.headers.authorization;
    if (!authHeader || !authHeader.startsWith("Bearer ")) {
      return null;
    }
    return authHeader.substring(7); // 去掉'Bearer '前缀
  }
}
```

### 4. 登出实现

最后，在用户登出时，我们需要将当前 token 加入黑名单：

```typescript
@UseGuards(JwtAuthGuard)
@Post('logout')
@HttpCode(HttpStatus.OK)
@ApiBearerAuth()
@ApiOperation({ summary: '用户退出登录' })
async logout(@Req() req: Request, @Res({ passthrough: true }) res: Response) {
  const refreshToken = req.cookies?.refreshToken;
  // 从请求上下文服务获取当前token
  const accessToken = this.requestContextService.getAccessToken();

  const result = await this.authService.logout(
    req.user['_id'],
    refreshToken,
    accessToken
  );

  // 清除刷新令牌cookie
  if (refreshToken) {
    res.clearCookie('refreshToken');
  }

  return result;
}
```

在 AuthenticationService 中：

```typescript
async logout(userId: string, refreshToken?: string, accessToken?: string): Promise<{ message: string }> {
  try {
    // 将当前访问令牌加入黑名单
    if (accessToken) {
      await this.tokenBlacklistService.addToBlacklist(accessToken, userId);
      this.logger.log(`用户 ${userId} 的访问令牌已加入黑名单`);
    }

    // 处理刷新令牌
    if (refreshToken) {
      await this.tokenService.invalidateRefreshToken(userId, refreshToken);
    }

    return { message: '已成功退出登录' };
  } catch (error) {
    this.logger.error(`退出登录过程中发生错误: ${(error as Error).message}`);
    return { message: '已成功退出登录' }; // 即使出错也返回成功，避免泄露系统错误
  }
}
```

## 设计要点解析

让我们分析一下这个实现中的几个关键设计：

### 1. 使用哈希值存储

我们没有直接存储完整的 JWT 令牌，而是存储其 SHA-256 哈希值。这样做有几个好处：

- **安全性**：即使 Redis 数据泄露，攻击者也无法获取原始 token
- **存储效率**：哈希值长度固定，比原始 token 更节省空间
- **查询效率**：哈希查询比字符串比较更高效

```typescript
private hashToken(token: string): string {
  return crypto.createHash('sha256').update(token).digest('hex');
}
```

### 2. 自动过期机制

我们巧妙地将 Redis 键的过期时间设置为与 token 剩余有效期相同：

```typescript
// 计算剩余过期时间（秒）
const currentTimestamp = Math.floor(Date.now() / 1000);
const ttl = Math.max(0, payload.exp - currentTimestamp);

// 如果token已过期，无需加入黑名单
if (ttl <= 0) {
  this.logger.debug("token已过期，无需加入黑名单");
  return true;
}

await this.redis.set(tokenKey, userId, "EX", ttl);
```

这样做的好处是：

- **自动清理**：过期的 token 会被 Redis 自动从黑名单中删除
- **资源优化**：不需要定期清理过期 token 的后台任务
- **存储优化**：黑名单大小不会无限增长

### 3. 失败默认允许

我们在处理 Redis 查询失败时采用了"失败默认允许"的策略：

```typescript
catch (error) {
  const err = error as Error;
  this.logger.error(`检查token黑名单状态失败: ${err.message}`);
  // 发生错误时，默认允许请求通过，避免系统锁死
  return false;
}
```

这是一种权衡：

- **优点**：即使 Redis 服务不可用，系统仍能继续工作
- **缺点**：可能导致已撤销的 token 在 Redis 故障期间仍然有效

这种设计适合大多数应用场景，但对于安全要求极高的场景，可能需要改为"失败默认拒绝"。

### 4. 前缀设计

使用前缀区分不同类型的 Redis 键：

```typescript
private readonly blacklistPrefix = 'bl_token:';
```

这种设计易于管理和调试，特别是在 Redis 实例被多个服务共享的情况下。

## 性能考虑

在高并发场景下，每个请求都要查询 Redis 可能会造成性能瓶颈。以下是一些可能的优化方案：

1. **本地缓存**：在应用服务器上维护一个小型内存缓存，缓存近期查询的 token 状态
2. **批量操作**：使用 Redis 的批量操作 API 减少网络往返
3. **读写分离**：使用 Redis 主从架构，读操作分布到多个从节点
4. **集群部署**：使用 Redis 集群分散压力

## 总结

通过 Redis 实现 Token 拉黑机制，我们巧妙地解决了 JWT 无法撤销的问题，同时保持了系统的高性能和可扩展性。这种实现不仅满足了用户登出和强制下线的需求，还为整个系统增加了一层额外的安全保障。

在实际项目中，这种机制已被证明是可靠且高效的。当然，根据具体的业务需求和系统规模，你可能需要对这个方案进行调整和优化。

希望这篇文章对你有所帮助，有任何问题欢迎交流讨论！

## 拓展阅读

- [Redis 官方文档](https://redis.io/documentation)
- [JWT 官方介绍](https://jwt.io/introduction)
- [OAuth2.0 令牌撤销规范](https://datatracker.ietf.org/doc/html/rfc7009)
