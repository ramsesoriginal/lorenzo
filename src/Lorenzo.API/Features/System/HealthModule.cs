using Carter;
using System.Reflection;

namespace Lorenzo.API.Features.System;

public class HealthModule : ICarterModule
{
    public void AddRoutes(IEndpointRouteBuilder app)
    {
        app.MapGet("/api/health", () => Results.Ok(new
        {
            status = "healthy",
            version = Assembly.GetExecutingAssembly().GetName().Version?.ToString() ?? "dev",
            timestamp = DateTime.UtcNow
        }))
        .WithName("Health")
        .WithTags("System")
        .AllowAnonymous();
    }
}
