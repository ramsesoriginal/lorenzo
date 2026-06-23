FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

COPY ["Lorenzo.API/Lorenzo.API.csproj", "Lorenzo.API/"]
COPY ["Lorenzo.Application/Lorenzo.Application.csproj", "Lorenzo.Application/"]
COPY ["Lorenzo.Domain/Lorenzo.Domain.csproj", "Lorenzo.Domain/"]
COPY ["Lorenzo.Infrastructure/Lorenzo.Infrastructure.csproj", "Lorenzo.Infrastructure/"]

RUN dotnet restore "Lorenzo.API/Lorenzo.API.csproj"

COPY . .


RUN dotnet publish "Lorenzo.API/Lorenzo.API.csproj" -c Release -o /app/publish

FROM mcr.microsoft.com/dotnet/aspnet:8.0-alpine AS runtime
WORKDIR /app
# RUN addgroup -S app && adduser -S app -G app # was already present
USER app
COPY --from=build /app/publish .
ENV ASPNETCORE_URLS=http://+:8080
EXPOSE 8080
ENTRYPOINT ["dotnet", "Lorenzo.API.dll"]
